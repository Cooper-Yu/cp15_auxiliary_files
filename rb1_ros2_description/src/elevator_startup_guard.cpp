#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <vector>
#include <gz/sim/System.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/components/Joint.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/components/JointPositionLimitsCmd.hh>
#include <gz/plugin/Register.hh>

// Opt-in simulation workaround, not a physical brake or a zero-limit repair.
class RB1ElevatorStartupGuard : public gz::sim::System,
    public gz::sim::ISystemConfigure,
    public gz::sim::ISystemConfigurePriority,
    public gz::sim::ISystemPreUpdate
{
public:
  PriorityType ConfigurePriority() override { return 100; }

  void Configure(const gz::sim::Entity &entity,
      const std::shared_ptr<const sdf::Element> &sdf,
      gz::sim::EntityComponentManager &, gz::sim::EventManager &) override
  {
    model = entity;
    directory = sdf->Get<std::string>("directory");
    if (!std::filesystem::is_directory(directory) ||
        std::filesystem::exists(directory / "release"))
      throw std::runtime_error("Guard requires a fresh private launch directory");
  }

  void PreUpdate(const gz::sim::UpdateInfo &info,
      gz::sim::EntityComponentManager &ecm) override
  {
    if (info.paused || released) return;
    const auto joint = ecm.EntityByComponents(gz::sim::components::Joint(),
        gz::sim::components::ParentEntity(model),
        gz::sim::components::Name("robot_elevator_platform_joint"));
    if (joint == gz::sim::kNullEntity) return;
    const double now = std::chrono::duration<double>(info.simTime).count();
    if (!locked) {
      std::ofstream(directory / "locked") << now;
      locked = true;
    }
    if (releaseStart < 0 && std::filesystem::exists(directory / "release"))
      releaseStart = now;
    // Restore [0, 0.034] over one simulation second, then stop writing limits.
    const double fraction = releaseStart < 0 ? 0 :
        std::clamp(now - releaseStart, 0.0, 1.0);
    const std::vector<gz::math::Vector2d> limits{
        {0.002 * (1 - fraction), 0.002 + 0.032 * fraction}};
    auto *component =
        ecm.Component<gz::sim::components::JointPositionLimitsCmd>(joint);
    if (component) component->Data() = limits;
    else ecm.CreateComponent(joint,
        gz::sim::components::JointPositionLimitsCmd(limits));
    if (fraction >= 1) {
      released = true;
      // The coordinator waits for later feedback, not this pre-physics sample.
      std::ofstream(directory / "released") << now;
    }
  }

private:
  gz::sim::Entity model = gz::sim::kNullEntity;
  std::filesystem::path directory;
  double releaseStart = -1;
  bool locked = false, released = false;
};

GZ_ADD_PLUGIN(RB1ElevatorStartupGuard, gz::sim::System,
    gz::sim::ISystemConfigure, gz::sim::ISystemConfigurePriority,
    gz::sim::ISystemPreUpdate)
