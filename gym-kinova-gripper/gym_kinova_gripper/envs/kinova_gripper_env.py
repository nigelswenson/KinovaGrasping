#!/usr/bin/env python3

###############
# Author: Yi Herng Ong
# Purpose: Kinova 3-fingered gripper in mujoco environment
# Summer 2019

###############


import gym
from gym import utils, spaces
from gym.utils import seeding
# from gym.envs.mujoco import mujoco_env
import numpy as np
from mujoco_py import MjViewer, load_model_from_path, MjSim
# from PID_Kinova_MJ import *
import math
import matplotlib.pyplot as plt
import time
import os, sys
from scipy.spatial.transform import Rotation as R
import random
import pickle
import pdb
import torch
import torch.nn as nn
import torch.nn.functional as F
import xml.etree.ElementTree as ET
import copy
from classifier_network import LinearNetwork
# resolve cv2 issue 
# sys.path.remove('/opt/ros/kinetic/lib/python2.7/dist-packages')
# frame skip = 20
# action update time = 0.002 * 20 = 0.04
# total run time = 40 (n_steps) * 0.04 (action update time) = 1.6

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
anj = False

class KinovaGripper_Env(gym.Env):
	metadata = {'render.modes': ['human']}
	def __init__(self, arm_or_end_effector="hand", frame_skip=4):
		self.file_dir = os.path.dirname(os.path.realpath(__file__))
		if arm_or_end_effector == "arm":
			self._model = load_model_from_path(self.file_dir + "/kinova_description/j2s7s300.xml")
			full_path = self.file_dir + "/kinova_description/j2s7s300.xml"
		elif arm_or_end_effector == "hand":
			pass
			self._model = load_model_from_path(self.file_dir + "/kinova_description/j2s7s300_end_effector.xml")
			# full_path = file_dir + "/kinova_description/j2s7s300_end_effector_v1.xml"
		else:
			print("CHOOSE EITHER HAND OR ARM")
			raise ValueError
		
		self._sim = MjSim(self._model)
		
		self._viewer = None
		# self.viewer = None

		##### Indicate object size (Nigel, data collection only) ###### 
		self.obj_size = "b"
		self.Grasp_Reward=False
		self._timestep = self._sim.model.opt.timestep
		self._torque = [0,0,0,0]
		self._velocity = [0,0,0,0]

		self._jointAngle = [0,0,0,0]
		self._positions = [] # ??
		self._numSteps = 0
		self._simulator = "Mujoco"
		self.action_scale = 0.0333
		self.max_episode_steps = 50
		# Parameters for cost function
		self.state_des = 0.20 
		self.initial_state = np.array([0.0, 0.0, 0.0, 0.0])
		self.frame_skip = frame_skip
		self.all_states = None
		self.action_space = spaces.Box(low=np.array([-0.8, -0.8, -0.8, -0.8]), high=np.array([0.8, 0.8, 0.8, 0.8]), dtype=np.float32) # Velocity action space
		# self.action_space = spaces.Box(low=np.array([-0.3, -0.3, -0.3, -0.3]), high=np.array([0.3, 0.3, 0.3, 0.3]), dtype=np.float32) # Velocity action space
		# self.action_space = spaces.Box(low=np.array([-1.5, -1.5, -1.5, -1.5]), high=np.array([1.5, 1.5, 1.5, 1.5]), dtype=np.float32) # Position action space
		self.state_rep = "local" # change accordingly
		# self.action_space = spaces.Box(low=np.array([-0.2]), high=np.array([0.2]), dtype=np.float32)
		# self.action_space = spaces.Box(low=np.array([-0.8, -0.8, -0.8]), high=np.array([0.8, 0.8, 0.8]), dtype=np.float32)

		min_hand_xyz = [-0.1, -0.1, 0.0, -0.1, -0.1, 0.0, -0.1, -0.1, 0.0,-0.1, -0.1, 0.0, -0.1, -0.1, 0.0,-0.1, -0.1, 0.0, -0.1, -0.1, 0.0]
		min_obj_xyz = [-0.1, -0.01, 0.0]
		min_joint_states = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
		min_obj_size = [0.0, 0.0, 0.0]
		min_finger_obj_dist = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
		min_obj_dot_prod = [0.0]
		min_f_dot_prod = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

		max_hand_xyz = [0.1, 0.1, 0.5, 0.1, 0.1, 0.5, 0.1, 0.1, 0.5,0.1, 0.1, 0.5, 0.1, 0.1, 0.5,0.1, 0.1, 0.5, 0.1, 0.1, 0.5]
		max_obj_xyz = [0.1, 0.7, 0.5]
		max_joint_states = [0.2, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0]
		max_obj_size = [0.5, 0.5, 0.5]
		max_finger_obj_dist = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]	
		max_obj_dot_prod = [1.0]
		max_f_dot_prod = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]


		# print()
		if self.state_rep == "global" or self.state_rep == "local":

			obs_min = min_hand_xyz + min_obj_xyz + min_joint_states + min_obj_size + min_finger_obj_dist + min_obj_dot_prod #+ min_f_dot_prod
			obs_min = np.array(obs_min)
			# print(len(obs_min))

			obs_max = max_hand_xyz + max_obj_xyz + max_joint_states + max_obj_size + max_finger_obj_dist + max_obj_dot_prod #+ max_f_dot_prod 
			obs_max = np.array(obs_max)
			# print(len(obs_max))

			self.observation_space = spaces.Box(low=obs_min , high=obs_max, dtype=np.float32)
		elif self.state_rep == "metric":
			obs_min = list(np.zeros(17)) + [-0.1, -0.1, 0.0] + min_obj_xyz + min_joint_states + min_obj_size + min_finger_obj_dist + min_dot_prod
			obs_max = list(np.full(17, np.inf)) + [0.1, 0.1, 0.5] + max_obj_xyz + max_joint_states + max_obj_size + max_finger_obj_dist + max_dot_prod
			self.observation_space = spaces.Box(low=np.array(obs_min) , high=np.array(obs_max), dtype=np.float32)

		elif self.state_rep == "joint_states":
			obs_min = min_joint_states + min_obj_xyz + min_obj_size + min_dot_prod
			obs_max = max_joint_states + max_obj_xyz + max_obj_size + max_dot_prod
			self.observation_space = spaces.Box(low=np.array(obs_min) , high=np.array(obs_max), dtype=np.float32)

		self.Grasp_net = LinearNetwork().to(device) 
		trained_model = "/home/graspinglab/NCS_data/trained_model_01_23_20_0111.pt"
		#trained_model = "/home/graspinglab/NCS_data/trained_model_01_23_20_2052local.pt"
		#trained_model = "/home/graspinglab/NCS_data/data_cube_9_grasp_classifier_10_17_19_1734.pt"
		# self.Grasp_net = GraspValid_net(54).to(device) 
		# trained_model = "/home/graspinglab/NCS_data/ExpertTrainedNet_01_04_20_0250.pt"
		model = torch.load(trained_model)
		self.Grasp_net.load_state_dict(model)
		self.Grasp_net.eval()


	# get 3D transformation matrix of each joint
	def _get_trans_mat(self, joint_geom_name):
		finger_joints = joint_geom_name	
		finger_pose = []
		empty = np.array([0,0,0,1])
		for each_joint in finger_joints:
			arr = []
			for axis in range(3):
				temp = np.append(self._sim.data.get_geom_xmat(each_joint)[axis], self._sim.data.get_geom_xpos(each_joint)[axis])
				arr.append(temp)
			arr.append(empty)
			arr = np.array(arr)
			finger_pose.append(arr)	
		return np.array(finger_pose)


	def _get_local_pose(self, mat):
		rot_mat = []
		trans = []
		# print(mat)
		for i in range(3):
			orient_temp = []

			for j in range(4):
				if j != 3:
					orient_temp.append(mat[i][j])
				elif j == 3:
					trans.append(mat[i][j])
			rot_mat.append(orient_temp)
		pose = list(trans) 
		# pdb.set_trace()
		return pose

	def _get_joint_states(self):
		arr = []
		for i in range(7):
			arr.append(self._sim.data.sensordata[i])

		return arr # it is a list

	# return global or local transformation matrix
	def _get_obs(self, state_rep=None):
		if state_rep == None:
			state_rep = self.state_rep

		range_data = self._get_rangefinder_data()
		# states rep
		obj_pose = self._get_obj_pose()
		obj_dot_prod = self._get_dot_product(obj_pose)
		wrist_pose  = self._sim.data.get_geom_xpos("palm")
		joint_states = self._get_joint_states()
		obj_size = self._sim.model.geom_size[-1] 
		finger_obj_dist = self._get_finger_obj_dist()

		palm = self._get_trans_mat(["palm"])[0]
		# for global
		finger_joints = ["f1_prox", "f2_prox", "f3_prox", "f1_dist", "f2_dist", "f3_dist"]
		# for inverse
		finger_joints_transmat = self._get_trans_mat(["f1_prox", "f2_prox", "f3_prox", "f1_dist", "f2_dist", "f3_dist"])
		fingers_6D_pose = []
		if state_rep == "global":			
			for joint in finger_joints:
				trans = self._sim.data.get_geom_xpos(joint)
				trans = list(trans)
				for i in range(3):
					fingers_6D_pose.append(trans[i])
			fingers_dot_prod = self._get_fingers_dot_product(fingers_6D_pose)
			fingers_6D_pose = fingers_6D_pose + list(wrist_pose) + list(obj_pose) + joint_states + [obj_size[0], obj_size[1], obj_size[2]*2] + finger_obj_dist + [obj_dot_prod] + fingers_dot_prod + range_data

		elif state_rep == "local":
			finger_joints_local = []
			palm_inverse = np.linalg.inv(palm)
			for joint in range(len(finger_joints_transmat)):
				joint_in_local_frame = np.matmul(finger_joints_transmat[joint], palm_inverse)
				pose = self._get_local_pose(joint_in_local_frame)
				for i in range(3):
					fingers_6D_pose.append(pose[i])
			fingers_dot_prod = self._get_fingers_dot_product(fingers_6D_pose)
			fingers_6D_pose = fingers_6D_pose + list(wrist_pose) + list(obj_pose) + joint_states + [obj_size[0], obj_size[1], obj_size[2]*2] + finger_obj_dist + [obj_dot_prod] + fingers_dot_prod + range_data

		elif state_rep == "metric":
			fingers_6D_pose = self._get_rangefinder_data()
			fingers_6D_pose = fingers_6D_pose + list(wrist_pose) + list(obj_pose) + joint_states + [obj_size[0], obj_size[1], obj_size[2]*2] + finger_obj_dist + [obj_dot_prod] #+ fingers_dot_prod

		elif state_rep == "joint_states":
			fingers_6D_pose = joint_states + list(obj_pose) + [obj_size[0], obj_size[1], obj_size[2]*2] + [obj_dot_prod] #+ fingers_dot_prod

		# print(joint_states[0:4])
		return fingers_6D_pose 

	def _get_finger_obj_dist(self):
		# finger_joints = ["palm", "f1_prox", "f2_prox", "f3_prox", "f1_dist", "f2_dist", "f3_dist"]
		finger_joints = ["palm_1", "f1_prox","f1_prox_1", "f2_prox", "f2_prox_1", "f3_prox", "f3_prox_1", "f1_dist", "f1_dist_1", "f2_dist", "f2_dist_1", "f3_dist", "f3_dist_1"]

		obj = self._get_obj_pose()
		dists = []
		for i in finger_joints:
			pos = self._sim.data.get_site_xpos(i)
			dist = np.absolute(pos[0:2] - obj[0:2])
			dist[0] -= 0.0175
			temp = np.linalg.norm(dist)
			dists.append(temp)
			# pdb.set_trace()
		return dists

	# get range data from 1 step of time 
	# Uncertainty: rangefinder could only detect distance to the nearest geom, therefore it could detect geom that is not object
	def _get_rangefinder_data(self):
		range_data = []
		for i in range(17):
			range_data.append(self._sim.data.sensordata[i+7])

		return range_data

	def _get_obj_pose(self):
		arr = self._sim.data.get_geom_xpos("object")
		return arr

	def _get_fingers_dot_product(self, fingers_6D_pose):
		fingers_dot_product = []
		for i in range(6):
			fingers_dot_product.append(self._get_dot_product(fingers_6D_pose[3*i:3*i+3]))
		return fingers_dot_product

	# Function to return dot product based on object location
	def _get_dot_product(self, obj_state):
		# obj_state = self._get_obj_pose()
		hand_pose = self._sim.data.get_body_xpos("j2s7s300_link_7")
		obj_state_x = abs(obj_state[0] - hand_pose[0])
		obj_state_y = abs(obj_state[1] - hand_pose[1])
		obj_vec = np.array([obj_state_x, obj_state_y])
		obj_vec_norm = np.linalg.norm(obj_vec)
		obj_unit_vec = obj_vec / obj_vec_norm

		center_x = abs(0.0 - hand_pose[0])
		center_y = abs(0.0 - hand_pose[1])
		center_vec = np.array([center_x, center_y])
		center_vec_norm = np.linalg.norm(center_vec)
		center_unit_vec = center_vec / center_vec_norm
		dot_prod = np.dot(obj_unit_vec, center_unit_vec)
		return dot_prod**20 # cuspy to get distinct reward

	def _get_reward_DataCollection(self):
		obj_target = 0.2
		obs = self._get_obs(state_rep="global") 
		if abs(obs[23] - obj_target) < 0.005 or (obs[23] >= obj_target):
			lift_reward = 1
			done = True
		else:
			lift_reward = 0
			done = False		
		return lift_reward, {}, done

	'''
	Reward function (Actual)
	'''
	def _get_reward(self):

		# object height target
		obj_target = 0.2

		#Grasp reward
		grasp_reward = 0.0
		obs = self._get_obs(state_rep="global") 
		network_inputs=obs[0:5]
		network_inputs=np.append(network_inputs,obs[6:23])
		network_inputs=np.append(network_inputs,obs[24:])
		inputs = torch.FloatTensor(np.array(network_inputs)).to(device)
		if np.max(np.array(obs[41:47])) < 0.035 or np.max(np.array(obs[35:41])) < 0.015: 
			outputs = self.Grasp_net(inputs).cpu().data.numpy().flatten()
			if (outputs >= 0.3) & (not self.Grasp_Reward):
				grasp_reward = 5.0
				self.Grasp_Reward=True
			else:
				grasp_reward = 0.0
		#grasp_reward = outputs
		
		if abs(obs[23] - obj_target) < 0.005 or (obs[23] >= obj_target):
			lift_reward = 50.0
			done = True
		else:
			lift_reward = 0.0
			done = False

		finger_reward = -np.sum((np.array(obs[41:47])) + (np.array(obs[35:41])))

		reward = 0.2*finger_reward + lift_reward + grasp_reward

		return reward, {}, done

	# only set proximal joints, cuz this is an underactuated hand
	def _set_state(self, states):
		self._sim.data.qpos[0] = states[0]
		self._sim.data.qpos[1] = states[1]
		self._sim.data.qpos[3] = states[2]
		self._sim.data.qpos[5] = states[3]
		self._sim.data.set_joint_qpos("object", [states[4], states[5], states[6], 1.0, 0.0, 0.0, 0.0])
		self._sim.forward()

	def _get_obj_size(self):
		return self._sim.model.geom_size[-1]


	def set_obj_size(self, default = False):
		hand_param = {}
		hand_param["span"] = 0.15
		hand_param["depth"] = 0.08
		hand_param["height"] = 0.15 # including distance between table and hand

		geom_types = ["box", "cylinder"]#, "sphere"]
		geom_sizes = ["s", "m", "b"]

		geom_type = random.choice(geom_types)
		geom_size = random.choice(geom_sizes)

		# Cube w: 0.1, 0.2, 0.3
		# Cylinder w: 0.1, 0.2, 0.3
		# Sphere w: 0.1, 0.2, 0.3

		# Cube & Cylinder
		width_max = hand_param["span"] * 0.3333 # 5 cm
		width_mid = hand_param["span"] * 0.2833 # 4.25 cm
		width_min = hand_param["span"] * 0.2333 # 3.5 cm
		width_choice = np.array([width_min, width_mid, width_max])

		height_max = hand_param["height"] * 0.80 # 0.12
		height_mid = hand_param["height"] * 0.73333 # 0.11
		height_min = hand_param["height"] * 0.66667 # 0.10
		height_choice = np.array([height_min, height_mid, height_max])

		# Sphere
		# radius_max = hand_param["span"] * 0.
		# radius_mid = hand_param["span"] * 0.2833 
		# radius_min = hand_param["span"] * 0.2333
		# radius_choice = np.array([radius_min, radius_mid, radius_max])

		if default:
			# print("here")
			return "box", np.array([width_choice[1]/2.0, width_choice[1]/2.0, height_choice[1]/2.0])
		else:

			if geom_type == "box": #or geom_type == "cylinder":
				if geom_size == "s":
					geom_dim = np.array([width_choice[0] / 2.0, width_choice[0] / 2.0, height_choice[0] / 2.0])
				if geom_size == "m":
					geom_dim = np.array([width_choice[1] / 2.0, width_choice[1] / 2.0, height_choice[1] / 2.0])
				if geom_size == "b":
					geom_dim = np.array([width_choice[2] / 2.0, width_choice[2] / 2.0, height_choice[2] / 2.0])
			if geom_type == "cylinder":
				if geom_size == "s":
					geom_dim = np.array([width_choice[0] / 2.0, height_choice[0] / 2.0])
				if geom_size == "m":
					geom_dim = np.array([width_choice[1] / 2.0, height_choice[1] / 2.0])
				if geom_size == "b":
					geom_dim = np.array([width_choice[2] / 2.0, height_choice[2] / 2.0])

			return geom_type, geom_dim, geom_size
							
	def gen_new_obj(self, default = False):
		file_dir = "./gym_kinova_gripper/envs/kinova_description"
		filename = "/objects.xml"
		tree = ET.parse(file_dir + filename)
		root = tree.getroot()
		d = default
		next_root = root.find("body")
		# print(next_root)
		# pick a shape and size
		geom_type, geom_dim, geom_size = self.set_obj_size(default = d)
		# if geom_type == "sphere":
		# 	next_root.find("geom").attrib["size"] = "{}".format(geom_dim[0])
		if geom_type == "box":
			next_root.find("geom").attrib["size"] = "{} {} {}".format(geom_dim[0], geom_dim[1], geom_dim[2])
		if geom_type == "cylinder":
			next_root.find("geom").attrib["size"] = "{} {}".format(geom_dim[0], geom_dim[1])
			
		next_root.find("geom").attrib["type"] = geom_type
		tree.write(file_dir + "/objects.xml")

		return geom_type, geom_dim, geom_size


	# 80 - 20 % 
	def sampling_pose_edge_normal(self, size, shape):
		if shape == "box":
			if size == "s" or size == "m": # now we assume medium and small objects can run the same poses.
				all_x_pose = [i*0.005-0.055 for i in range(23)] # 22 poses
				edge_x = all_x_pose[:3] + all_x_pose[-3:]
				normal_x = all_x_pose[3:-3]
				edge_or_normal = np.random.choice(np.array(["normal", "edge"]), p = [0.8, 0.2])
				if edge_or_normal == "normal":
					rand_x = random.choice(normal_x)
					rand_y = random.uniform(0.0, min(0.04, 0.02 + (0.04 - abs(rand_x)))) # random y position from 0.0 to corresponding newly calculated max y
				elif edge_or_normal == "edge":
					rand_x = random.choice(edge_x)
					rand_y = 0.0
			elif size == "b":
				all_x_pose = [i*0.005-0.03 for i in range(13)] # 12 poses
				edge_x = all_x_pose[:2] + all_x_pose[-2:]
				normal_x = all_x_pose[2:-2]
				edge_or_normal = np.random.choice(np.array(["normal", "edge"]), p = [0.8, 0.2])
				if edge_or_normal == "normal":
					rand_x = random.choice(normal_x)
					rand_y = random.uniform(0.0, min(0.02, 0.02 - abs(rand_x))) # random y position from 0.0 to corresponding newly calculated max y
				elif edge_or_normal == "edge":
					rand_x = random.choice(edge_x)
					rand_y = 0.0
		elif shape == "cyl":
			if size == "s":
				all_x_pose = [i*0.005-0.05 for i in range(21)] # 22 poses
				edge_x = all_x_pose[:2] + all_x_pose[-2:]
				normal_x = all_x_pose[2:-2]
				edge_or_normal = np.random.choice(np.array(["normal", "edge"]), p = [0.8, 0.2])
				if edge_or_normal == "normal":
					rand_x = random.choice(normal_x)
					rand_y = random.uniform(0.0, min(0.04, 0.02 + (0.04 - abs(rand_x)))) # random y position from 0.0 to corresponding newly calculated max y
				elif edge_or_normal == "edge":
					rand_x = random.choice(edge_x)
					rand_y = 0.0
			if size == "m":
				all_x_pose = [i*0.005-0.04 for i in range(17)] # 22 poses
				edge_x = all_x_pose[:2] + all_x_pose[-2:]
				normal_x = all_x_pose[2:-2]
				edge_or_normal = np.random.choice(np.array(["normal", "edge"]), p = [0.8, 0.2])
				if edge_or_normal == "normal":
					rand_x = random.choice(normal_x)
					rand_y = random.uniform(0.0, min(0.03, 0.02 + (0.03 - abs(rand_x)))) # random y position from 0.0 to corresponding newly calculated max y
				elif edge_or_normal == "edge":
					rand_x = random.choice(edge_x)
					rand_y = 0.0
			elif size == "b":
				all_x_pose = [i*0.005-0.03 for i in range(13)] # 12 poses
				edge_x = all_x_pose[:2] + all_x_pose[-2:]
				normal_x = all_x_pose[2:-2]
				edge_or_normal = np.random.choice(np.array(["normal", "edge"]), p = [0.8, 0.2])
				if edge_or_normal == "normal":
					rand_x = random.choice(normal_x)
					rand_y = random.uniform(0.0, min(0.02, 0.02 - abs(rand_x))) # random y position from 0.0 to corresponding newly calculated max y
				elif edge_or_normal == "edge":
					rand_x = random.choice(edge_x)
					rand_y = 0.0 				

		return rand_x, rand_y

	def randomize_initial_pose(self, collect_data, size):
		# geom_type, geom_dim, geom_size = self.gen_new_obj()
		# geom_size = "s"
		geom_size = size

		# self._model = load_model_from_path(self.file_dir + "/kinova_description/j2s7s300_end_effector_v1.xml")
		# self._sim = MjSim(self._model)

		if geom_size == "s":
			if not collect_data:
				x = [0.05, 0.04, 0.03, 0.02, -0.05, -0.04, -0.03, -0.02]
				y = [0.0, 0.02, 0.03, 0.04]
				rand_x = random.choice(x)
				rand_y = 0.0				
				if rand_x == 0.05 or rand_x == -0.05:
					rand_y = 0.0
				elif rand_x == 0.04 or rand_x == -0.04:
					rand_y = random.uniform(0.0, 0.02)
				elif rand_x == 0.03 or rand_x == -0.03:
					rand_y = random.uniform(0.0, 0.03)
				elif rand_x == 0.02 or rand_x == -0.02:
					rand_y = random.uniform(0.0, 0.04)
			else:
				x = [0.04, 0.03, 0.02, -0.04, -0.03, -0.02]
				y = [0.0, 0.02, 0.03, 0.04]
				rand_x = random.choice(x)
				rand_y = 0.0					
				if rand_x == 0.04 or rand_x == -0.04:
					rand_y = random.uniform(0.0, 0.02)
				elif rand_x == 0.03 or rand_x == -0.03:
					rand_y = random.uniform(0.0, 0.03)
				elif rand_x == 0.02 or rand_x == -0.02:
					rand_y = random.uniform(0.0, 0.04)				
		if geom_size == "m":
			x = [0.04, 0.03, 0.02, -0.04, -0.03, -0.02]
			y = [0.0, 0.02, 0.03]
			rand_x = random.choice(x)
			rand_y = 0.0
			if rand_x == 0.04 or rand_x == -0.04:
				rand_y = 0.0
			elif rand_x == 0.03 or rand_x == -0.03:
				rand_y = random.uniform(0.0, 0.02)
			elif rand_x == 0.02 or rand_x == -0.02:
				rand_y = random.uniform(0.0, 0.03)
		if geom_size == "b":
			x = [0.03, 0.02, -0.03, -0.02]
			y = [0.0, 0.02]
			rand_x = random.choice(x)
			rand_y = 0.0
			if rand_x == 0.03 or rand_x == -0.03:
				rand_y = 0.0
			elif rand_x == 0.02 or rand_x == -0.02:
				rand_y = random.uniform(0.0, 0.02)
		# return rand_x, rand_y, geom_dim[-1]
		# print(rand_x, rand_y)
		return rand_x, rand_y


		# medium x = [0.04, 0.03, 0.02]
		# med y = [0.0, 0.02, 0.03]
		# large x = [0.03, 0.02] 
		# large y = [0.0, 0.02]

	def experiment(self, exp_num, stage_num, test=False):
		objects = {}

		if not test:

			# ------ Experiment 1 ------- #
			if exp_num == 1:
					
				# Exp 1 Stage 1: Change size ---> 
				if stage_num == 1:
					objects["sbox"] = "/kinova_description/j2s7s300_end_effector.xml"
					objects["bbox"] = "/kinova_description/j2s7s300_end_effector_v1_bbox.xml"

					# Testing Exp 1 Stage 1

				# Exp 1 Stage 2: Change shape
				if stage_num == 2:
					objects["sbox"] = "/kinova_description/j2s7s300_end_effector.xml"
					objects["bbox"] = "/kinova_description/j2s7s300_end_effector_v1_bbox.xml"				
					objects["scyl"] = "/kinova_description/j2s7s300_end_effector_v1_scyl.xml"
					objects["bcyl"] = "/kinova_description/j2s7s300_end_effector_v1_bcyl.xml"	

			# ------ Experiment 2 ------- #
			elif exp_num == 2:
				
				# Exp 2 Stage 1: Change shape
				if stage_num == 1:
					objects["sbox"] = "/kinova_description/j2s7s300_end_effector.xml"
					objects["scyl"] = "/kinova_description/j2s7s300_end_effector_v1_scyl.xml"

				# Exp 2 Stage 2: Change size
				if stage_num == 2:
					objects["sbox"] = "/kinova_description/j2s7s300_end_effector.xml"
					objects["scyl"] = "/kinova_description/j2s7s300_end_effector_v1_scyl.xml"
					objects["bbox"] = "/kinova_description/j2s7s300_end_effector_v1_bbox.xml"
					objects["bcyl"] = "/kinova_description/j2s7s300_end_effector_v1_bcyl.xml"
				
				# Testing Exp 2
				# objects["mbox"] = "/kinova_description/j2s7s300_end_effector_v1_mbox.xml"
				# objects["mcyl"] = "/kinova_description/j2s7s300_end_effector_v1_mcyl.xml"
				# objects["bbox"] = "/kinova_description/j2s7s300_end_effector_v1_bbox.xml"
				# objects["bcyl"] = "/kinova_description/j2s7s300_end_effector_v1_bcyl.xml"
				# objects["sbox"] = "/kinova_description/j2s7s300_end_effector.xml"
				# objects["scyl"] = "/kinova_description/j2s7s300_end_effector_v1_scyl.xml"
			# ------ Experiment 3 ------ #
			elif exp_num == 3:
				# Mix all
				objects["sbox"] = "/kinova_description/j2s7s300_end_effector.xml"
				objects["bbox"] = "/kinova_description/j2s7s300_end_effector_v1_bbox.xml"
				objects["scyl"] = "/kinova_description/j2s7s300_end_effector_v1_scyl.xml"
				objects["bcyl"] = "/kinova_description/j2s7s300_end_effector_v1_bcyl.xml"
				

			else:
				print("Enter Valid Experiment Number")
				raise ValueError
		else:
			# Test objects:
			objects["mcyl"] = "/kinova_description/j2s7s300_end_effector_v1_mcyl.xml"
			objects["mbox"] = "/kinova_description/j2s7s300_end_effector_v1_mbox.xml"	

		return objects

	def randomize_all(self, test):

		### Choose an experiment ###
		objects = self.experiment(3, 1, test) 

		# Get random shape
		random_shape = np.random.choice(list(objects.keys()))

		# Load model
		self._model = load_model_from_path(self.file_dir + objects[random_shape])

		# self._model = load_model_from_path(self.file_dir + objects["mcyl"])
		if (random_shape=="sbox") |(random_shape=="mbox")|(random_shape=="bbox"):
			self.obj_shape=1
		elif (random_shape=="scyl")|(random_shape=="mcyl")|(random_shape=="bcyl"):
			self.obj_shape=0
		# global anj
		# if (anj == False):
		# 	self._sim = MjSim(self._model)
		# 	anj = True
		self._sim = MjSim(self._model)

		# if random_shape == "sbox" or random_shape == "scyl":
		# 	x, y = self.randomize_initial_pose(False, "s")
		# 	z = 0.05
		# elif random_shape == "mbox" or random_shape == "mcyl":
		# 	x, y = self.randomize_initial_pose(False, "m")
		# 	z = 0.055
		# elif random_shape == "bbox" or random_shape == "bcyl":
		# 	x, y = self.randomize_initial_pose(False, "b")
		# 	z = 0.06			
		# else:
		# 	print("size and shape are incorrect")
		# 	raise ValueError
		x, y = self.sampling_pose_edge_normal(random_shape[0], random_shape[1:])
		z = self._get_obj_size()[-1]

		return x, y, z

	def randomize_initial_pos_data_collection(self):
		# print(self._sim.model.geom_size[-1])
		if self.obj_size == "s":
			x = [0.05, 0.04, 0.03, 0.02, -0.05, -0.04, -0.03, -0.02]
			y = [0.0, 0.02, 0.03, 0.04]
			rand_x = random.choice(x)
			if rand_x == 0.05 or rand_x == -0.05:
				rand_y = 0.0
			elif rand_x == 0.04 or rand_x == -0.04:
				rand_y = random.uniform(0.0, 0.02)
			elif rand_x == 0.03 or rand_x == -0.03:
				rand_y = random.uniform(0.0, 0.03)
			elif rand_x == 0.02 or rand_x == -0.02:
				rand_y = random.uniform(0.0, 0.04)
		if self.obj_size == "m":
			x = [0.04, 0.03, 0.02, -0.04, -0.03, -0.02]
			y = [0.0, 0.02, 0.03]
			rand_x = random.choice(x)
			if rand_x == 0.04 or rand_x == -0.04:
				rand_y = 0.0
			elif rand_x == 0.03 or rand_x == -0.03:
				rand_y = random.uniform(0.0, 0.02)
			elif rand_x == 0.02 or rand_x == -0.02:
				rand_y = random.uniform(0.0, 0.03)
		if self.obj_size == "b":
			x = [0.03, 0.02, -0.03, -0.02]
			y = [0.0, 0.02]
			rand_x = random.choice(x)
			if rand_x == 0.03 or rand_x == -0.03:
				rand_y = 0.0
			elif rand_x == 0.02 or rand_x == -0.02:
				rand_y = random.uniform(0.0, 0.02)

		z = self._sim.model.geom_size[-1][-1]
		return rand_x, rand_y, z	

	def reset(self):
		x, y, z = self.randomize_all(False) # for RL training
		# x, y, z = self.randomize_all(True) # For testing policy
		
		self.all_states = np.array([0.0, 0.0, 0.0, 0.0, x, y, z])
		self._set_state(self.all_states)
		states = self._get_obs()
		self.t_vel = 0
		self.prev_obs = []
		self.Grasp_Reward=False
		return states

	def render(self, mode='human'):
		if self._viewer is None:
			self._viewer = MjViewer(self._sim)
			self._viewer.render()

	def close(self):
		if self._viewer is not None:
			self._viewer = None

	def seed(self, seed=None):
		self.np_random, seed = seeding.np_random(seed)
		return [seed]

	###################################################
	##### ---- Action space : Joint Velocity ---- #####
	###################################################
	def step(self, action):
		total_reward = 0
		for _ in range(self.frame_skip):
			if action[0] < 0.0:
				self._sim.data.ctrl[0] = 0.0
			else:	
				self._sim.data.ctrl[0] = (action[0] / 0.8) * 0.2
				# self._sim.data.ctrl[0] = action[0]

			for i in range(3):
				# vel = action[i]
				if action[i+1] < 0.0:
					self._sim.data.ctrl[i+1] = 0.0
				else:	
					self._sim.data.ctrl[i+1] = action[i+1]
			self._sim.step()

		obs = self._get_obs()

		### Get this reward for RL training ###
		total_reward, info, done = self._get_reward()
		### Get this reward for data collection ###
		# total_reward, info, done = self._get_reward_DataCollection()

		# print(obs[15:18], self._get_dot_product(obs[15:18]))

		# print(self._get_dot_product)
		return obs, total_reward, done, info
	#####################################################

	###################################################
	##### ---- Action space : Joint Angle ---- ########
	###################################################
	# def step(self, action):
	# 	total_reward = 0
	# 	for _ in range(self.frame_skip):
	# 		self.pos_control(action)
	# 		self._sim.step()

	# 	obs = self._get_obs()
	# 	total_reward, info, done = self._get_reward()
	# 	self.t_vel += 1
	# 	self.prev_obs.append(obs)
	# 	# print(self._sim.data.qpos[0], self._sim.data.qpos[1], self._sim.data.qpos[3], self._sim.data.qpos[5])
	# 	return obs, total_reward, done, info

	# def pos_control(self, action):
	# 	# position 
	# 	# print(action)

	# 	self._sim.data.ctrl[0] = (action[0] / 1.5) * 0.2
	# 	self._sim.data.ctrl[1] = action[1]
	# 	self._sim.data.ctrl[2] = action[2]
	# 	self._sim.data.ctrl[3] = action[3]
	# 	# velocity 
	# 	if abs(action[0] - 0.0) < 0.0001:
	# 		self._sim.data.ctrl[4] = 0.0
	# 	else:
	# 		self._sim.data.ctrl[4] = 0.1
	# 		# self._sim.data.ctrl[4] = (action[0] - self.prev_action[0] / 25)		

	# 	if abs(action[1] - 0.0) < 0.001:
	# 		self._sim.data.ctrl[5] = 0.0
	# 	else:
	# 		self._sim.data.ctrl[5] = 0.01069
	# 		# self._sim.data.ctrl[5] = (action[1] - self.prev_action[1] / 25)	

	# 	if abs(action[2] - 0.0) < 0.001:
	# 		self._sim.data.ctrl[6] = 0.0
	# 	else:
	# 		self._sim.data.ctrl[6] = 0.01069
	# 		# self._sim.data.ctrl[6] = (action[2] - self.prev_action[2] / 25)	

	# 	if abs(action[3] - 0.0) < 0.001:
	# 		self._sim.data.ctrl[7] = 0.0						
	# 	else:
	# 		self._sim.data.ctrl[7] = 0.01069
	# 		# self._sim.data.ctrl[7] = (action[3] - self.prev_action[3] / 25)	
	
		# self.prev_action = np.array([self._sim.data.qpos[0], self._sim.data.qpos[1], self._sim.data.qpos[3], self._sim.data.qpos[5]])
		# self.prev_action = np.array([self._sim.data.qpos[0], self._sim.data.qpos[1], self._sim.data.qpos[3], self._sim.data.qpos[5]])

	#####################################################


class GraspValid_net(nn.Module):
	def __init__(self, state_dim):
		super(GraspValid_net, self).__init__()
		self.l1 = nn.Linear(state_dim, 256)
		self.l2 = nn.Linear(256, 256)
		self.l3 = nn.Linear(256, 1)

	def forward(self, state):
		# pdb.set_trace()

		a = F.relu(self.l1(state))
		a = F.relu(self.l2(a))
		a =	torch.sigmoid(self.l3(a))
		return a
