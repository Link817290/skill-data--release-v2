# Build a replay buffer seed

Use `materials/trajectory_unified.npz`, `materials/grasp_phase_segments.json`, and `materials/ppo_script.py` as the available project inputs for the existing pick bottle trajectory.
Create a compact replay buffer seed that samples the corrected trajectory, assigns each sampled frame to its grasp phase, summarizes its joint state, and records suitable action, reward, and downstream routing metadata.
Deliver only `output/replay_buffer_seed.jsonl` with one JSON object per line in ascending `t` order, using top level keys `t`, `phase`, `obs`, `action_ref`, `reward_target`, and `use_for`, where `obs` contains `qpos_mean_abs`, `qpos_dim`, and `base_z`, `action_ref` contains `finger_residual_limit_rad`, and `reward_target` contains `tracking`, `contact`, and `lift`.
