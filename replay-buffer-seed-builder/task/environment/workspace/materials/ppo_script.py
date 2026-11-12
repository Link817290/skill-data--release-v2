"""
RoboWheel V1.7-PPO-D2: D2 keypoint-IK baseline + PPO residual RL + domain randomization.

Pipeline:
  - Base trajectory: V1.7 calibrated 6-DOF (FoundationPose + MANO wrist)
  - Finger baseline: D2 MANO keypoint IK (22 DOF per hand)
  - RL residual: PPO +/-0.08 rad on finger joints
  - Domain randomization: bottle mass/friction, joint damping, obs noise, action delay

Builds on:
  - step_rl_v17_calibrated_6dof.py (V1.7 kinematic replay)
  - step_final_unified.py (PPO reward structure)
  - mano_keypoint_ik.py (D2 IK solver)
"""
import os, json, sys, time
os.environ["MUJOCO_GL"] = "egl"

import numpy as np
import mujoco
import cv2
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from stable_baselines3.common.callbacks import BaseCallback
from scipy.spatial.transform import Rotation as Rot
from scipy.ndimage import uniform_filter1d

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPIDER_MANO   = os.path.join(BASE_DIR, 'spider/spider/assets/robots/mano')
OUT_DIR       = os.path.join(BASE_DIR, 'output/rl_v17_ppo_d2')
MANO_PATH     = os.path.join(BASE_DIR, 'output/pick_bottle_video/mano_results.json')
BOTTLE_VISUAL = os.path.abspath(os.path.join(BASE_DIR, 'output/bottle_recon/bottle_visual.obj'))
CALIB_PATH    = os.path.join(BASE_DIR, 'output/calibrated_trajectory.npz')
FPOSE_PATH    = os.path.join(BASE_DIR, 'output/bottle_6dof_poses.npz')
MANO_KP_PATH  = os.path.join(BASE_DIR, 'output/mano_keypoints.npz')
R_M2S_PATH    = os.path.join(BASE_DIR, 'output/R_MANO_TO_SPIDER.npz')

R_FPOSE2SIM = Rot.from_euler('x', 90, degrees=True).as_matrix()


# ---------------------------------------------------------------------------
# Domain randomization config
# ---------------------------------------------------------------------------
DR_CONFIG = {
    'bottle_mass':    (0.15, 0.25),     # kg, nominal 0.20
    'bottle_friction': (1.4, 2.6),      # nominal 2.0
    'joint_damping_scale': (0.85, 1.15),
    'obs_noise_std':  0.005,            # rad for joints, m for positions
    'action_delay_frames': (0, 2),      # 0-2 frame delay
}


def load_calibration_data():
    """Load all pre-computed calibration data once (shared across envs)."""
    # Wrist calibration
    if os.path.exists(R_M2S_PATH):
        d = np.load(R_M2S_PATH)
        R_M2S_RIGHT, R_M2S_LEFT = d['right'], d['left']
    else:
        R_M2S_RIGHT = R_M2S_LEFT = Rot.from_euler('z', 90, degrees=True).as_matrix()

    # D2 keypoint IK finger angles
    if os.path.exists(MANO_KP_PATH):
        print("  [finger mapping] D2: keypoint IK")
        from mano_keypoint_ik import solve_all_frames
        kp = np.load(MANO_KP_PATH)
        rh_mjcf = os.path.join(SPIDER_MANO, 'right.xml')
        lh_mjcf = os.path.join(SPIDER_MANO, 'left.xml')
        I = np.eye(3)
        rf = solve_all_frames(kp['right'], I, rh_mjcf, 'right', kp['valid_right'])
        lf = solve_all_frames(kp['left'],  I, lh_mjcf, 'left',  kp['valid_left'])
        N_mano = len(rf)
    else:
        print("  [finger mapping] D1 fallback: Euler decomposition")
        N_mano, rf, lf = _load_mano_fingers_d1()

    # Calibrated trajectory (hand-in-bottle relative poses)
    calib = np.load(CALIB_PATH)
    hib_t = calib['hand_in_bottle_t'].copy()   # (N,2,3)
    hib_R = calib['hand_in_bottle_R'].copy()   # (N,2,3,3)
    valid = calib['valid']                     # (N,2)
    scale = float(calib['scale'])
    hand_cam_t = calib['hand_cam_t_metric'].copy()  # (N,2,3)

    # FoundationPose bottle trajectory
    fpose = np.load(FPOSE_PATH)['poses']  # (N, 4, 4)
    N = min(N_mano, len(hib_t), len(fpose))

    # Truncate all to N
    hib_t = hib_t[:N]; hib_R = hib_R[:N]; valid = valid[:N]
    fpose = fpose[:N]; rf = rf[:N]; lf = lf[:N]
    hand_cam_t = hand_cam_t[:N]

    # Fill invalid frames (forward-fill + back-fill)
    for side in range(2):
        first_valid = next((i for i in range(N) if valid[i, side]), None)
        if first_valid is None:
            hib_t[:, side] = 0.0; hib_R[:, side] = np.eye(3); continue
        for i in range(first_valid):
            hib_t[i, side] = hib_t[first_valid, side]
            hib_R[i, side] = hib_R[first_valid, side]
        last_t, last_R = hib_t[first_valid, side].copy(), hib_R[first_valid, side].copy()
        for i in range(first_valid, N):
            if valid[i, side]:
                last_t, last_R = hib_t[i, side].copy(), hib_R[i, side].copy()
            else:
                hib_t[i, side], hib_R[i, side] = last_t, last_R

    # FPose -> sim frame
    hib_t = hib_t @ R_FPOSE2SIM.T
    hib_R = np.einsum('ij,nsjk->nsik', R_FPOSE2SIM, hib_R)

    # Intro-card noise filtering
    grip_start = next((i for i in range(N) if valid[i, 0] and valid[i, 1]), 0)
    if grip_start > 0:
        for side in range(2):
            hib_t[:grip_start, side] = hib_t[grip_start, side]
            hib_R[:grip_start, side] = hib_R[grip_start, side]
        rf[:grip_start] = rf[grip_start]
        lf[:grip_start] = lf[grip_start]

    # Heavy smoothing to reduce HaMeR jitter (prevents knocking bottle over)
    hib_t[:, 0] = uniform_filter1d(hib_t[:, 0], size=15, axis=0)
    hib_t[:, 1] = uniform_filter1d(hib_t[:, 1], size=15, axis=0)
    rf = uniform_filter1d(rf, size=7, axis=0)
    lf = uniform_filter1d(lf, size=7, axis=0)

    # Compute bottle world trajectory (with FPose override)
    R_bc = fpose[:, :3, :3]; t_bc = fpose[:, :3, 3]
    R_cw = R_FPOSE2SIM @ np.linalg.inv(R_bc[0])
    t_cw = np.array([0.0, 0.0, 0.26]) - R_cw @ t_bc[0]

    palm_world_raw = np.einsum('ij,nsj->nsi', R_cw, np.nan_to_num(hand_cam_t)) + t_cw
    initial_t = (R_cw @ t_bc[0] + t_cw).copy()

    body_t_world = np.tile(initial_t, (N, 1))
    for fi in range(N):
        if fi < grip_start:
            continue
        contribs = []
        for side in range(2):
            if valid[fi, side]:
                contribs.append(palm_world_raw[fi, side] - hib_t[fi, side])
        if contribs:
            body_t_world[fi] = np.mean(contribs, axis=0)
        else:
            body_t_world[fi] = body_t_world[fi - 1]
    if grip_start < N - 1:
        body_t_world[grip_start:] = uniform_filter1d(body_t_world[grip_start:], size=5, axis=0)

    return {
        'N': N,
        'hib_t': hib_t,
        'hib_R': hib_R,
        'valid': valid,
        'rf': rf,
        'lf': lf,
        'body_t_world': body_t_world,
        'R_M2S_RIGHT': R_M2S_RIGHT,
        'R_M2S_LEFT': R_M2S_LEFT,
        'grip_start': grip_start,
    }


def _load_mano_fingers_d1():
    """D1 fallback: Euler decomposition mapping."""
    with open(MANO_PATH) as f:
        results = json.load(f)
    frame_dict = {}
    for r in results:
        frame_dict.setdefault(r['img_name'], {})[('right' if r['is_right'] else 'left')] = r
    keys = sorted(frame_dict.keys())
    N = len(keys)
    CURL_GAIN = 1.7; THUMB_GAIN = 1.4

    def decompose_yz(R):
        return Rot.from_matrix(R).as_euler('YZX')[:2]
    def decompose_z(R):
        return Rot.from_matrix(R).as_euler('YZX')[1]
    def decompose_xyz(R):
        return Rot.from_matrix(R).as_euler('XYZ')

    def mano_to_artimano(hp):
        joints = np.zeros(22)
        g = CURL_GAIN
        for base_j, mano_slice in [(0, [0,1,2]), (4, [3,4,5]), (8, [6,7,8]), (12, [9,10,11])]:
            y, z = decompose_yz(hp[mano_slice[0]])
            joints[base_j] = y; joints[base_j+1] = g * z
            joints[base_j+2] = g * decompose_z(hp[mano_slice[1]])
            joints[base_j+3] = g * decompose_z(hp[mano_slice[2]])
        tg = THUMB_GAIN
        t = decompose_xyz(hp[12])
        joints[16], joints[17], joints[18] = t[0], t[1], tg * t[2]
        ty, tz = decompose_yz(hp[13])
        joints[19], joints[20] = ty, tg * tz
        joints[21] = tg * decompose_z(hp[14])
        return joints

    rf = np.zeros((N, 22)); lf = np.zeros((N, 22))
    for i, k in enumerate(keys):
        fr = frame_dict[k]
        if 'right' in fr: rf[i] = mano_to_artimano(np.array(fr['right']['mano_hand_pose']))
        if 'left'  in fr: lf[i] = mano_to_artimano(np.array(fr['left']['mano_hand_pose']))
    rf = uniform_filter1d(rf, size=5, axis=0)
    lf = uniform_filter1d(lf, size=5, axis=0)
    return N, rf, lf


class V17PPOEnv(gym.Env):
    """V1.7 calibrated base + D2 IK fingers + PPO residual + domain randomization.

    Key design: both base and finger joints are driven via data.ctrl (actuators),
    NOT by writing qpos directly. Spider MANO XML already provides 28 actuators per
    hand (6 base + 22 finger). The base actuators have gain=1000 (stiff tracking),
    finger actuators gain=300. RL residual is added on top of the finger reference.
    """
    metadata = {"render_modes": ["rgb_array"]}

    def __init__(self, calib_data=None, render_mode=None, use_domain_rand=True, phase=1):
        super().__init__()
        self.render_mode = render_mode
        self.use_dr = use_domain_rand
        self.cd = calib_data
        self.phase = phase  # 1=contact only, 2=contact+lift

        self.N = self.cd['N']
        self.max_steps = self.N

        self.model, self.data = self._build()
        self._find_ids()

        # RL acts on base position residual (6: xyz × 2 hands) + finger residual (44)
        # Base residual ±2cm (small — just fix reconstruction error, not invent new motion)
        # Finger residual ±0.15 rad
        act_lo = np.concatenate([np.full(6, -0.02), np.full(44, -0.15)])
        act_hi = np.concatenate([np.full(6, 0.02),  np.full(44, 0.15)])
        self.action_space = spaces.Box(act_lo, act_hi, dtype=np.float32)

        # obs: 44 finger joints + 6 base pos + 7 bottle pose + 30 fingertips + 1 timestep = 88
        obs_dim = 44 + 6 + 7 + 30 + 1
        self.observation_space = spaces.Box(-10, 10, shape=(obs_dim,), dtype=np.float32)

        self.step_count = 0
        self.prev_action = np.zeros(50)
        self.bottle_init_z = 0
        self.action_buffer = []  # for action delay DR

    def _build(self):
        os.chdir(SPIDER_MANO)
        hr = mujoco.MjSpec.from_file('right.xml')
        hl = mujoco.MjSpec.from_file('left.xml')

        s = mujoco.MjSpec()
        s.option.gravity = [0, 0, -9.81]
        s.option.timestep = 0.002
        s.option.impratio = 10
        s.option.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
        w = s.worldbody

        l = w.add_light(); l.pos=[0,-0.3,0.5]; l.dir=[0,0.2,-1]; l.diffuse=[1,1,1]; l.castshadow=True
        l2 = w.add_light(); l2.pos=[0.3,0.2,0.4]; l2.dir=[-0.2,-0.1,-0.5]; l2.diffuse=[0.4,0.4,0.4]

        f = w.add_geom(); f.type=mujoco.mjtGeom.mjGEOM_PLANE; f.size=[0.5,0.5,0.01]; f.rgba=[0.92,0.92,0.92,1]
        t = w.add_geom(); t.type=mujoco.mjtGeom.mjGEOM_BOX; t.size=[0.18,0.14,0.01]
        t.pos=[0,0,0.15]; t.rgba=[0.38,0.28,0.20,1]; t.friction=[1.0,0.005,0.0001]

        # Bottle with collision
        if os.path.exists(BOTTLE_VISUAL):
            bottle_mesh = s.add_mesh(); bottle_mesh.name="bottle_mesh"; bottle_mesh.file=BOTTLE_VISUAL

        bottle = w.add_body(); bottle.name="bottle"; bottle.pos=[0,0,0.26]
        bj = bottle.add_freejoint(); bj.name="bottle_joint"
        if os.path.exists(BOTTLE_VISUAL):
            bv = bottle.add_geom(); bv.type=mujoco.mjtGeom.mjGEOM_MESH; bv.meshname="bottle_mesh"
            bv.quat = Rot.from_euler('x', 90, degrees=True).as_quat(scalar_first=True).tolist()
            bv.rgba=[0.20,0.55,0.85,0.45]; bv.contype=0; bv.conaffinity=0; bv.group=1; bv.mass=0
        bg = bottle.add_geom(); bg.type=mujoco.mjtGeom.mjGEOM_CYLINDER; bg.name="bottle_col"
        bg.size=[0.030,0.075,0]; bg.rgba=[0.15,0.50,0.85,0.15]; bg.mass=0.20
        bg.friction=[3.0,0.01,0.001]; bg.contype=1; bg.conaffinity=1

        # Hands: enable collision on collision geoms BEFORE attaching to scene.
        # MuJoCo caches collision filtering at compile time, so contype must be
        # set in the spec, not after compilation.
        for hand_spec, prefix in [(hr, "rh_"), (hl, "lh_")]:
            # Walk all geoms in the hand spec and enable collision on primitives
            self._enable_collision_in_spec(hand_spec.worldbody)
            w.add_frame().attach_body(hand_spec.worldbody.first_body(), prefix, "")

        model = s.compile()
        return model, mujoco.MjData(model)

    @staticmethod
    def _enable_collision_in_spec(body):
        """Recursively enable + enlarge collision geoms for stable grasping.

        Original Spider MANO capsules are 5-8mm radius — too small for area
        contact. We scale them up ~2.5x to simulate soft fingertip contact
        (~15-20mm effective radius). Also increase friction significantly.

        contype=2 avoids hand self-collision while allowing hand-bottle contact.
        """
        geom = body.first_geom()
        while geom is not None:
            if geom.type != mujoco.mjtGeom.mjGEOM_MESH:
                geom.contype = 2
                geom.conaffinity = 1
                geom.friction = [3.0, 0.01, 0.001]  # high friction (soft skin)
                # Enlarge collision primitives for area contact
                if geom.type == mujoco.mjtGeom.mjGEOM_CAPSULE:
                    geom.size[0] *= 2.5  # radius: 8mm → 20mm
                    geom.size[1] *= 1.5  # half-length: modest increase
                elif geom.type == mujoco.mjtGeom.mjGEOM_BOX:
                    geom.size[0] *= 2.0  # palm box wider
                    geom.size[1] *= 2.0
                    geom.size[2] *= 2.0
            geom = body.next_geom(geom)
        child = body.first_body()
        while child is not None:
            V17PPOEnv._enable_collision_in_spec(child)
            child = body.next_body(child)

    def _find_ids(self):
        self.bottle_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'bottle')
        self.bottle_qadr = self.model.jnt_qposadr[
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'bottle_joint')]

        # Actuator indices: base (6) and finger (22) per hand
        self.rh_base_acts = []  # 6 actuators: pos_x/y/z + rot_x/y/z
        self.rh_finger_acts = []  # 22 actuators: finger joints
        self.lh_base_acts = []
        self.lh_finger_acts = []
        for i in range(self.model.nu):
            nm = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) or ""
            if nm.startswith("rh_"):
                if "pos_" in nm or "rot_" in nm:
                    self.rh_base_acts.append(i)
                else:
                    self.rh_finger_acts.append(i)
            elif nm.startswith("lh_"):
                if "pos_" in nm or "rot_" in nm:
                    self.lh_base_acts.append(i)
                else:
                    self.lh_finger_acts.append(i)

        # Finger joint IDs (for reading qpos in obs)
        self.rh_jnts = []; self.lh_jnts = []
        for i in range(self.model.njnt):
            nm = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, i) or ""
            if "_pos_" in nm or "_rot_" in nm: continue
            if nm.startswith("rh_"): self.rh_jnts.append(i)
            elif nm.startswith("lh_"): self.lh_jnts.append(i)

        # Fingertip body IDs for reward computation
        self.tip_ids = []
        for i in range(self.model.nbody):
            nm = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_BODY, i) or ""
            if any(f in nm for f in ["index3", "middle3", "pinky3", "ring3", "thumb3"]):
                self.tip_ids.append(i)

        # Hand base body IDs
        self.base_r_bid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'rh_right_palm')
        self.base_l_bid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'lh_left_palm')

        # Bottle collision geom ID for DR
        self.bottle_geom_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, 'bottle_col')

    def _apply_domain_rand(self, rng):
        """Randomize physics parameters at episode start."""
        if not self.use_dr:
            return
        dr = DR_CONFIG

        # Bottle mass
        mass = rng.uniform(*dr['bottle_mass'])
        self.model.body_mass[self.bottle_id] = mass

        # Bottle friction
        fric = rng.uniform(*dr['bottle_friction'])
        if self.bottle_geom_id >= 0:
            self.model.geom_friction[self.bottle_geom_id, 0] = fric

        # Joint damping scale (finger joints only)
        damp_scale = rng.uniform(*dr['joint_damping_scale'])
        for jid in self.rh_jnts + self.lh_jnts:
            self.model.dof_damping[self.model.jnt_dofadr[jid]] *= damp_scale

        # Action delay
        self.action_delay = rng.randint(dr['action_delay_frames'][0],
                                        dr['action_delay_frames'][1] + 1)

    def _set_ctrl_base(self, fi, base_residual=None):
        """Drive hand bases from V1.7 reconstructed trajectory + RL residual.

        Position: bottle_actual_pos + hib_t[fi] + RL_residual
        Orientation: hib_R[fi] @ R_M2S (pure reconstruction, no RL)
        Bottle: free body, physics only.
        """
        cd = self.cd
        bottle_pos = self.data.xpos[self.bottle_id].copy()

        if base_residual is None:
            base_residual = np.zeros(6)

        for side_idx, base_acts, R_M2S in [
            (0, self.rh_base_acts, cd['R_M2S_RIGHT']),
            (1, self.lh_base_acts, cd['R_M2S_LEFT']),
        ]:
            # Position: reconstructed offset (with lateral scale) + RL residual
            # Scale the lateral (XY) component of hib_t to bring hands closer
            # to the bottle surface. HaMeR/FoundationPose overestimates the
            # hand-bottle distance; scaling preserves trajectory shape while
            # making physical contact possible.
            offset = cd['hib_t'][fi, side_idx].copy()
            offset[:2] *= 0.5  # scale lateral by 0.5 (Z axis = bottle axis, untouched)
            target_pos = bottle_pos + offset
            residual_offset = base_residual[side_idx * 3:(side_idx + 1) * 3]
            target_pos = target_pos + residual_offset

            # Orientation: pure reconstruction (hib_R @ R_M2S)
            target_R = cd['hib_R'][fi, side_idx] @ R_M2S
            euler = Rot.from_matrix(target_R).as_euler('xyz')

            for k in range(3):
                self.data.ctrl[base_acts[k]] = target_pos[k]
                self.data.ctrl[base_acts[3 + k]] = euler[k]

    def _get_obs(self):
        # Finger joint angles
        joints = np.zeros(44, dtype=np.float32)
        for j, jid in enumerate(self.rh_jnts[:22]):
            joints[j] = self.data.qpos[self.model.jnt_qposadr[jid]]
        for j, jid in enumerate(self.lh_jnts[:22]):
            joints[22+j] = self.data.qpos[self.model.jnt_qposadr[jid]]

        # Base positions (right xyz + left xyz)
        base = np.zeros(6, dtype=np.float32)
        if self.base_r_bid >= 0:
            base[:3] = self.data.xpos[self.base_r_bid]
        if self.base_l_bid >= 0:
            base[3:6] = self.data.xpos[self.base_l_bid]

        # Bottle pose
        bp = self.data.xpos[self.bottle_id].astype(np.float32)
        bq = self.data.xquat[self.bottle_id].astype(np.float32)

        # Fingertip positions
        tips = np.zeros(30, dtype=np.float32)
        for j, tid in enumerate(self.tip_ids[:10]):
            tips[j*3:(j+1)*3] = self.data.xpos[tid]

        ts = np.array([self.step_count / self.max_steps], dtype=np.float32)
        obs = np.concatenate([joints, base, bp, bq, tips, ts])

        # Observation noise (DR)
        if self.use_dr and DR_CONFIG['obs_noise_std'] > 0:
            obs += self.np_random.normal(0, DR_CONFIG['obs_noise_std'], size=obs.shape).astype(np.float32)

        return obs

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.step_count = 0
        self.prev_action = np.zeros(50)
        self.action_buffer = []
        self.action_delay = 0
        self.sustained_contact_count = 0  # consecutive frames with finger contact

        # Domain randomization
        rng = np.random.RandomState(seed if seed is not None else None)
        self._apply_domain_rand(rng)

        # Forward pass to initialize xpos before accessing body positions
        mujoco.mj_forward(self.model, self.data)

        # Set initial ctrl from reconstructed trajectory (f0)
        self._set_ctrl_base(0)
        cd = self.cd
        for j, ai in enumerate(self.rh_finger_acts[:22]):
            jid = self.model.actuator_trnid[ai, 0]
            jr = self.model.jnt_range[jid] if jid >= 0 else [-3, 3]
            self.data.ctrl[ai] = np.clip(cd['rf'][0, j], jr[0], jr[1])
        for j, ai in enumerate(self.lh_finger_acts[:22]):
            jid = self.model.actuator_trnid[ai, 0]
            jr = self.model.jnt_range[jid] if jid >= 0 else [-3, 3]
            self.data.ctrl[ai] = np.clip(cd['lf'][0, j], jr[0], jr[1])

        # Initialize hand base positions via qpos for fast convergence.
        # Use reconstructed f0 positions with lateral scale (matching _set_ctrl_base)
        bottle_pos = self.data.xpos[self.bottle_id].copy()
        for side_idx, base_acts, R_M2S in [
            (0, self.rh_base_acts, cd['R_M2S_RIGHT']),
            (1, self.lh_base_acts, cd['R_M2S_LEFT']),
        ]:
            offset = cd['hib_t'][0, side_idx].copy()
            offset[:2] *= 0.5
            target_pos = bottle_pos + offset
            target_R = cd['hib_R'][0, side_idx] @ R_M2S
            euler = Rot.from_matrix(target_R).as_euler('xyz')
            for k in range(3):
                jid = self.model.actuator_trnid[base_acts[k], 0]
                self.data.qpos[self.model.jnt_qposadr[jid]] = target_pos[k]
                jid_r = self.model.actuator_trnid[base_acts[3 + k], 0]
                self.data.qpos[self.model.jnt_qposadr[jid_r]] = euler[k]

        # Short settle with full physics
        for _ in range(50):
            mujoco.mj_step(self.model, self.data)

        self.bottle_init_z = self.data.xpos[self.bottle_id][2]
        return self._get_obs(), {}

    def step(self, action):
        self.step_count += 1
        fi = min(self.step_count - 1, self.N - 1)

        # Action delay (DR): buffer actions, apply delayed version
        self.action_buffer.append(action.copy())
        delay = min(self.action_delay, len(self.action_buffer) - 1)
        effective_action = self.action_buffer[-(delay + 1)]

        # Split action: [0:6] = base position residual, [6:50] = finger residual
        base_residual = effective_action[:6]
        finger_residual = effective_action[6:]

        # Base actuators: reconstructed trajectory + RL position residual
        self._set_ctrl_base(fi, base_residual=base_residual)

        # Finger actuators: D2 IK baseline + RL residual (NO curl boost)
        cd = self.cd
        for j, ai in enumerate(self.rh_finger_acts[:22]):
            jid = self.model.actuator_trnid[ai, 0]
            jr = self.model.jnt_range[jid] if jid >= 0 else [-3, 3]
            ref = cd['rf'][fi, j]
            self.data.ctrl[ai] = np.clip(ref + finger_residual[j], jr[0], jr[1])

        for j, ai in enumerate(self.lh_finger_acts[:22]):
            jid = self.model.actuator_trnid[ai, 0]
            jr = self.model.jnt_range[jid] if jid >= 0 else [-3, 3]
            ref = cd['lf'][fi, j]
            self.data.ctrl[ai] = np.clip(ref + finger_residual[22 + j], jr[0], jr[1])

        # Step physics (10 sub-steps per control step)
        for _ in range(10):
            try:
                mujoco.mj_step(self.model, self.data)
            except Exception:
                mujoco.mj_resetData(self.model, self.data)
                break

        obs = self._get_obs()
        bpos = self.data.xpos[self.bottle_id]
        bz = bpos[2]
        lift = bz - self.bottle_init_z

        # === REWARD: two-phase training ===
        # Phase 1: learn stable finger contact (no lift reward)
        # Phase 2: add lift reward on top of learned grasp

        # --- Shared components ---
        # 1. Track: penalize deviation from reconstruction
        base_res = action[:6]
        finger_res = action[6:]
        r_track = -np.sum(base_res**2) * 50.0 - np.sum(finger_res**2) * 5.0

        # 2. Fingertips approach bottle
        tip_dists = [np.linalg.norm(self.data.xpos[tid] - bpos) for tid in self.tip_ids[:10]]
        r_geo = -np.mean(tip_dists) * 20.0 if tip_dists else 0.0

        # 3. Smooth actions
        r_dyn = -np.sum((action - self.prev_action)**2) * 1.0
        self.prev_action = action.copy()

        # 4. Count finger vs palm contacts with bottle
        n_finger_con = 0
        n_palm_con = 0
        bottle_gid = self.bottle_geom_id
        for ci in range(self.data.ncon):
            c = self.data.contact[ci]
            g1n = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, c.geom1) or ""
            g2n = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, c.geom2) or ""
            if c.geom1 != bottle_gid and c.geom2 != bottle_gid:
                continue
            hand_geom = g1n if c.geom2 == bottle_gid else g2n
            if "palm" in hand_geom:
                n_palm_con += 1
            elif "rh_" in hand_geom or "lh_" in hand_geom:
                n_finger_con += 1

        # Finger contacts (primary), palm contacts (minor)
        r_con = min(n_finger_con, 10) * 5.0 + min(n_palm_con, 4) * 0.5

        # 5. Stability: penalize knocking bottle over
        r_stable = -max(0, self.bottle_init_z - bz) * 15.0

        # 6. Proximity
        r_prox = -np.mean(tip_dists) * 15.0 if tip_dists else 0.0

        # 7. Sustained contact tracking
        if n_finger_con >= 2:
            self.sustained_contact_count += 1
        else:
            self.sustained_contact_count = 0

        # Multi-finger grasp bonus (scales with sustained duration)
        r_grasp = 0.0
        if n_finger_con >= 2 and bz >= self.bottle_init_z - 0.02:
            r_grasp = 5.0 + min(self.sustained_contact_count, 20) * 0.5
        if n_finger_con >= 4:
            r_grasp += 10.0

        # 8. Bottle upright bonus
        bottle_quat_w = abs(self.data.xquat[self.bottle_id][0])
        r_upright = 3.0 if bottle_quat_w > 0.95 else -5.0  # strongly penalize tipping

        # --- Phase-specific ---
        r_lift = 0.0
        if self.phase == 2:
            capped_lift = min(max(0, lift), 0.20)
            # Only reward lift if sustained finger contact (>=3 consecutive frames)
            # AND bottle is still upright — prevents fling/tip exploits
            if self.sustained_contact_count >= 3 and bottle_quat_w > 0.90:
                r_lift = capped_lift * 300.0
            if lift > 0.25:
                r_stable -= (lift - 0.25) * 100.0  # stronger anti-launch penalty

        reward = r_track + r_geo + r_dyn + r_con + r_lift + r_stable + r_prox + r_grasp + r_upright

        done = self.step_count >= self.max_steps
        if bz < 0.10:
            done = True
            reward -= 3.0

        return obs, reward, done, False, {
            'lift_cm': lift * 100,
            'contacts': self.data.ncon,
            'finger_con': n_finger_con,
            'palm_con': n_palm_con,
            'res_norm': np.linalg.norm(action),
            'r_track': r_track,
            'r_geo': r_geo,
            'r_con': r_con,
            'r_lift': r_lift,
            'r_prox': r_prox,
        }

    def render(self):
        if not hasattr(self, '_renderer'):
            self.model.vis.global_.offwidth = 640
            self.model.vis.global_.offheight = 480
            self._renderer = mujoco.Renderer(self.model, height=480, width=640)
            self._cam = mujoco.MjvCamera()
            self._cam.type = mujoco.mjtCamera.mjCAMERA_FREE
            self._cam.lookat[:] = [0, 0, 0.28]
            self._cam.distance = 0.60; self._cam.azimuth = 145; self._cam.elevation = -25
        self._renderer.update_scene(self.data, self._cam)
        return self._renderer.render()


class ProgressCallback(BaseCallback):
    """Print training progress periodically."""
    def __init__(self, print_freq=10_000, verbose=0):
        super().__init__(verbose)
        self.print_freq = print_freq

    def _on_step(self):
        if self.num_timesteps % self.print_freq == 0:
            infos = self.locals.get('infos', [])
            lifts = [i.get('lift_cm', 0) for i in infos if isinstance(i, dict)]
            fcons = [i.get('finger_con', 0) for i in infos if isinstance(i, dict)]
            pcons = [i.get('palm_con', 0) for i in infos if isinstance(i, dict)]
            avg_lift = np.mean(lifts) if lifts else 0
            avg_fcon = np.mean(fcons) if fcons else 0
            avg_pcon = np.mean(pcons) if pcons else 0
            print(f"  [{self.num_timesteps:>7d}] lift={avg_lift:.1f}cm  finger_con={avg_fcon:.1f}  palm_con={avg_pcon:.1f}")
        return True


def evaluate_and_render(model, calib_data, out_dir, phase=2):
    """Run deterministic evaluation and save videos."""
    env = V17PPOEnv(calib_data=calib_data, render_mode="rgb_array", use_domain_rand=False, phase=phase)
    obs, _ = env.reset(seed=42)
    frames = []
    total_r = 0; max_lift = 0; max_con = 0

    for i in range(calib_data['N']):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, _, info = env.step(action)
        total_r += reward
        max_lift = max(max_lift, info['lift_cm'])
        max_con = max(max_con, info['contacts'])

        img = env.render()
        bgr = img[:, :, ::-1].copy()

        # Phase label
        t = i / max(calib_data['N'] - 1, 1)
        if t < 0.25: phase = "REACH"
        elif t < 0.50: phase = "APPROACH"
        elif t < 0.70: phase = "GRASP"
        else: phase = "LIFT"

        cv2.putText(bgr, f"[{phase}] f{i} con={info['contacts']} lift={info['lift_cm']:.1f}cm",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 220, 0), 1)
        cv2.putText(bgr, f"res={info['res_norm']:.3f} track={info['r_track']:.1f} geo={info['r_geo']:.1f}",
                    (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 180, 255), 1)
        frames.append(bgr)
        if done:
            break

    print(f"\n=== Evaluation Results ===")
    print(f"  Total reward:  {total_r:.1f}")
    print(f"  Max contacts:  {max_con}")
    print(f"  Max lift:      {max_lift:.1f} cm")
    print(f"  Frames:        {len(frames)}")

    # Save sim video
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    sim_mp4 = os.path.join(out_dir, 'v17_ppo_d2.mp4')
    w = cv2.VideoWriter(sim_mp4, fourcc, 15, (640, 480))
    for f in frames: w.write(f)
    w.release()

    # Keyframes
    for idx in [0, 20, 40, 60, 80, 100, 120, min(150, len(frames)-1)]:
        if idx < len(frames):
            cv2.imwrite(os.path.join(out_dir, f'kf_{idx:04d}.jpg'), frames[idx])

    # Comparison video (HaMeR | sim)
    ov_dir = os.path.join(BASE_DIR, 'output/pick_bottle_video')
    if os.path.isdir(ov_dir):
        ovs = sorted([f for f in os.listdir(ov_dir) if f.endswith('_overlay.jpg')])
        if ovs:
            pw, ph = 640, 480
            cmp_mp4 = os.path.join(out_dir, 'comparison.mp4')
            wc = cv2.VideoWriter(cmp_mp4, fourcc, 15, (pw * 2, ph + 25))
            for i, f in enumerate(frames):
                oi = min(int(i / len(frames) * len(ovs)), len(ovs) - 1)
                ov = cv2.resize(cv2.imread(os.path.join(ov_dir, ovs[oi])), (pw, ph))
                panels = np.hstack([ov, f])
                lb = np.ones((25, pw * 2, 3), dtype=np.uint8) * 35
                cv2.putText(lb, "Video + HaMeR (MANO)", (5, 17),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 1)
                cv2.putText(lb, "V1.7 D2-IK + PPO + DomainRand", (pw + 5, 17),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 0), 1)
                wc.write(np.vstack([lb, panels]))
            wc.release()

            # GIF
            import subprocess
            subprocess.run(['ffmpeg', '-y', '-i', cmp_mp4,
                '-vf', 'fps=8,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse',
                os.path.join(out_dir, 'comparison.gif')], capture_output=True)

    return max_lift, max_con


def train_phase(calib_data, phase, total_timesteps, pretrained_model=None, pretrained_vecnorm=None):
    """Train one phase of the two-phase curriculum."""
    phase_dir = os.path.join(OUT_DIR, f'phase{phase}')
    os.makedirs(phase_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Phase {phase}: {'Contact training (no lift)' if phase == 1 else 'Contact + Lift training'}")
    print(f"{'='*60}")

    env = DummyVecEnv([
        lambda: V17PPOEnv(calib_data=calib_data, use_domain_rand=True, phase=phase)
        for _ in range(16)
    ])

    if pretrained_vecnorm and os.path.exists(pretrained_vecnorm):
        env = VecNormalize.load(pretrained_vecnorm, env)
        env.training = True
        print(f"  Loaded VecNormalize from Phase {phase-1}")
    else:
        env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0, clip_reward=10.0)

    ppo_kwargs = dict(
        learning_rate=3e-4,
        n_steps=512,
        batch_size=512,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
        verbose=1,
    )

    if pretrained_model and os.path.exists(pretrained_model + '.zip'):
        ppo = PPO.load(pretrained_model, env=env, **ppo_kwargs)
        print(f"  Loaded model from Phase {phase-1}")
    else:
        ppo = PPO("MlpPolicy", env, **ppo_kwargs)

    t0 = time.time()
    ppo.learn(
        total_timesteps=total_timesteps,
        progress_bar=True,
        callback=ProgressCallback(print_freq=100_000),
    )
    elapsed = time.time() - t0
    print(f"  Phase {phase} done in {elapsed:.0f}s ({elapsed/60:.1f}min)")

    model_path = os.path.join(phase_dir, f'ppo_phase{phase}')
    vecnorm_path = os.path.join(phase_dir, f'vecnormalize_phase{phase}.pkl')
    ppo.save(model_path)
    env.save(vecnorm_path)
    print(f"  Saved: {model_path}")

    return ppo, model_path, vecnorm_path, phase_dir


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 60)
    print("V1.7-PPO-D2: Two-Phase Curriculum Training")
    print("  Phase 1: Stable finger contact (no lift)")
    print("  Phase 2: Lift with finger grasp")
    print("=" * 60)

    print("\nLoading calibration data...")
    calib_data = load_calibration_data()
    print(f"  Frames: {calib_data['N']}, Grip start: f{calib_data['grip_start']}")

    # Phase 1: learn to grip (no lift reward)
    ppo1, model1, vecnorm1, dir1 = train_phase(
        calib_data, phase=1, total_timesteps=1_000_000)

    print(f"\n--- Phase 1 Evaluation ---")
    max_lift1, max_con1 = evaluate_and_render(ppo1, calib_data, dir1)

    # Phase 2: learn to lift (initialized from Phase 1)
    ppo2, model2, vecnorm2, dir2 = train_phase(
        calib_data, phase=2, total_timesteps=1_000_000,
        pretrained_model=model1, pretrained_vecnorm=vecnorm1)

    print(f"\n--- Phase 2 Evaluation ---")
    max_lift2, max_con2 = evaluate_and_render(ppo2, calib_data, dir2)

    # Also save final model to top-level dir
    ppo2.save(os.path.join(OUT_DIR, 'ppo_v17_d2'))

    print(f"\n{'='*60}")
    print(f"Phase 1: lift={max_lift1:.1f}cm  contacts={max_con1}")
    print(f"Phase 2: lift={max_lift2:.1f}cm  contacts={max_con2}")
    print(f"Output: {OUT_DIR}/")

    print(f"\n{'=' * 60}")
    print(f"Done! Output: {OUT_DIR}/")
    for fn in sorted(os.listdir(OUT_DIR)):
        sz = os.path.getsize(os.path.join(OUT_DIR, fn))
        print(f"  {fn} ({sz/1024:.0f} KB)")
    print(f"\nKey metrics: lift={max_lift:.1f}cm  contacts={max_con}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
