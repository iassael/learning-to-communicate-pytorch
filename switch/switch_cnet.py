"""

DRQN-based agent that learns to communicate with other agents to play 
the Switch game.

"""
import torch
from torch import nn
from torch.nn import functional as F
from torch.autograd import Variable

from modules.bn_rnn import RNN


class SwitchCNet(nn.Module):

	def __init__(self, opt):
		super(SwitchCNet, self).__init__()

		self.opt = opt
		self.comm_size = opt.game_comm_bits
		self.init_param_range = (-0.08, 0.08)

		# Set up inputs
		self.agent_lookup = nn.Embedding(opt.game_nagents, opt.model_rnn_size)
		self.state_lookup = nn.Embedding(2, opt.model_rnn_size)

		# Action aware
		if opt.model_action_aware:
			self.prev_action_lookup = nn.Embedding(self.total_action_space, opt.model_rnn_size)

		# Communication enabled
		# Note if SwitchCNet is training, DRU should add noise + non-linearity
		# If SwitchCnet is executing in test mode, DRU should discretize messages
		if opt.game_comm_bits > 0 and opt.game_nagents > 1:
			self.messages_mlp = nn.Sequential()
			if opt.model_bn:
				self.messages_mlp.add_module('batchnorm1', nn.BatchNormalization(comm_size))
			self.messages_mlp.add_module('linear1', nn.Linear(comm_size, opt.model_rnn_size))
			if opt.model_comm_narrow:
				self.messages_mlp.add_module('relu1', nn.ReLU(inplace=True))

		# Set up RNN
		rnn_mode = opt.model_rnn or 'gru'
		dropout_rate = opt.model_rnn_dropout_rate or 0
		self.rnn = bn_rnn.RNN(
			mode=rnn_mode, input_size=opt.model_rnn_size, hidden_size=opt.model_rnn_size, 
			num_layers=2, use_bn=True, bn_max_t=16, dropout_rate=dropout_rate)

		# Set up outputs
		self.outputs = nn.Sequential()
		if dropout_rate > 0:
			self.outputs.add_module('dropout1', nn.Dropout(dropout_rate))
		self.outputs.add_module('linear1', nn.Linear(opt.model_rnn_size, opt.model_rnn_size))
		self.outputs.add_module('relu1', nn.ReLU(inplace=True))
		self.outputs.add_module('linear2', nn.Linear(opt.model_rnn_size, opt.game_action_space_total))

		self.reset_params()
	
	def _reset_linear_module(self, 	layer):
		layer.weight.data.uniform_(*self.init_param_range)
		layer.bias.data.uniform_(*self.init_param_range)

	def reset_params(self):
		self.agent_lookup.fill_(*self.init_param_range)
		self.state_lookup.fill_(*self.init_param_range)
		self.prev_action_lookup.fill_(*self.init_param_range)
		self._reset_linear_module(self.messages_mlp.linear1)
		self.rnn.reset_params()
		self._reset_linear_module(self.outputs.linear1)
		self._reset_linear_module(self.outputs.linear2)

	def forward(self, agent_index, observation, prev_action, messages):
		z_a = self.agent_lookup(agent_index)
		z_o = self.state_lookup(observation)
		z_u = self.prev_action_lookup(prev_action)
		z_m = self.messages_mlp(messages.view(-1, self.comm_size).contiguous())

		z = z_a + z_0 + z_u + z_m

		model_rnn_size = self.opt.model_rnn_size
		rnn_out, _ = self.rnn(z)
		outputs = self.outputs(rnn_out[:, -1, :])

		return outputs
