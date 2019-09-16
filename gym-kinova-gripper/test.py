# from envs.kinova_gripper_env import KinovaGripper_Env
# env.action_space.sample()
import gym
from gym import spaces
import numpy as np
env = gym.make('gym_kinova_gripper:kinovagripper-v0')

env.reset()

# finger = np.array([1.0, 0.0, 0.0])
finger = np.array([0.25])

# print(env.action_space)
for _ in range(50):
	obs, reward, done, _ = env.step(finger)
	# env.render()
	print("reward", reward)
	# print("obs", len(obs))
	# print("done", done)
	# print(type(env._sim.data.time))

	# if abs(env._sim.data.time - 2.000) < 0.0000001:
	# 	print(env._sim.data.get_joint_qpos("j2s7s300_joint_finger_1") / 2) 


print(env._sim.data.time)

# obs_min = np.array([-0.1, -0.1, 0.0, -360, -360, -360, -0.1, -0.1, 0.0, -360, -360, -360,
# 	-0.1, -0.1, 0.0, -360, -360, -360,-0.1, -0.1, 0.0, -360, -360, -360,
# 	-0.1, -0.1, 0.0, -360, -360, -360,-0.1, -0.1, 0.0, -360, -360, -360, 
# 	-0.1, -0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
# obs_max = np.array([0.1, 0.1, 0.3, 360, 360, 360, 0.1, 0.1, 0.3, 360, 360, 360,
# 	0.1, 0.1, 0.3, 360, 360, 360,0.1, 0.1, 0.3, 360, 360, 360,
# 	0.1, 0.1, 0.3, 360, 360, 360,0.1, 0.1, 0.3, 360, 360, 360,
# 	0.1, 0.7, 0.3, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0])

# # print(len(obs_max))
# # obs_min = np.zeros(17)
# # obs_max = obs_min + np.Inf
# # print(type(np.Inf))
# a = spaces.Box(low=obs_min, high=obs_max, dtype=np.float32)
# b = spaces.Box(low=np.array([-1.0, -1.0, -1.0]), high=np.array([1.0, 1.0, 1.0]), dtype=np.float32)
# print(b.shape)


# obs_min = np.zeros(17) 
# obs_max = obs_min + np.Inf
# c = spaces.Box(low=obs_min , high=obs_max, dtype=np.float32)
# print(c.shape)