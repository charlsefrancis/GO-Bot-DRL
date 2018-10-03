from user_simulator import UserSimulator
from emc import EMC
from dqn_agent import DQNAgent
from state_tracker import StateTracker
import pickle
import json


# Load Constants Json into Dict
CONSTANTS_FILE_PATH = 'constants.json'
with open(CONSTANTS_FILE_PATH) as f:
    constants = json.load(f)

# Load File Path Constants
file_path_dict = constants['file_paths']
DATABASE_FILE_PATH = file_path_dict['database']
DICT_FILE_PATH = file_path_dict['dict']
USER_GOALS_FILE_PATH = file_path_dict['user_goals']

# Load Run Constants
run_dict = constants['run']
WARMUP_MEM = run_dict['warmup_mem']
NUM_EP_TRAIN = run_dict['num_ep_train']
TRAIN_FREQ = run_dict['train_freq']
NUM_EP_TEST = run_dict['num_ep_test']
MAX_ROUND_NUM = run_dict['max_round_num']
SUCCESS_RATE_THRESHOLD = run_dict['success_rate_threshold']

# Todo: make sure these were loaded in correctly
# Load Movie DB
database = pickle.load(open(DATABASE_FILE_PATH, 'rb'), encoding='latin1')
# Load Movie Dict
db_dict = pickle.load(open(DICT_FILE_PATH, 'rb'), encoding='latin1')
# Load Goal File
user_goals = pickle.load(open(USER_GOALS_FILE_PATH, 'rb'), encoding='latin1')

# Init. Objects
user_sim = UserSimulator(user_goals, constants)
emc_0 = EMC(db_dict, constants)
state_tracker = StateTracker(database, constants)
dqn_agent = DQNAgent(state_tracker.get_state_size(), constants)


# Warm-Up loop
def warmup_run():
    print('Warmup Started...')
    ep = 0
    total_step = 0
    done_warmup = False
    while not done_warmup:
        ep_reset()
        ep += 1
        ep_step = 0
        ep_reward = 0
        done = False
        while not done:
            # Get state tracker state
            state = state_tracker.get_state()
            # Agent takes action given state tracker's representation of dialogue
            agent_action_index, agent_action = dqn_agent.get_action(state, use_rule=True)
            # Update state tracker with the agent's action
            round_num = state_tracker.update_state_agent(agent_action)
            # User sim. takes action given agent action
            user_action, reward, done, succ = user_sim.step(agent_action, round_num)
            ep_reward += reward
            if not done:
                # Infuse error into semantic frame level user sim. action
                emc_0.infuse_error(user_action)
                # Update state tracker with user sim. action
            state_tracker.update_state_user(user_action)
            # Add memory
            next_state = state_tracker.get_state(done)
            dqn_agent.add_experience(state, agent_action_index, reward, next_state, done)

            ep_step += 1
            total_step += 1

            if total_step == WARMUP_MEM:
                done_warmup = True
                done = True

        print('Episode: {} Succ.: {} Reward: {}'.format(ep, succ, ep_reward))

    print("...Warmup Ended")


# Training Loop
def train_run():
    print("Train Started...")
    ep = 0
    period_succ_total = 0
    succ_rate_best = 0.0
    while ep < NUM_EP_TRAIN:
        ep_reset()
        # Inner loop (by conversation)
        ep += 1
        ep_reward = 0
        done = False
        while not done:
            # Get state tracker state
            state = state_tracker.get_state()
            # Agent takes action given state tracker's representation of dialogue
            agent_action_index, agent_action = dqn_agent.get_action(state)
            # Update state tracker with the agent's action
            round_num = state_tracker.update_state_agent(agent_action)
            # User sim. takes action given agent action
            user_action, reward, done, succ = user_sim.step(agent_action, round_num)
            ep_reward += reward
            if not done:
                # Infuse error into semantic frame level user sim. action
                emc_0.infuse_error(user_action)
            # Update state tracker with user sim. action
            state_tracker.update_state_user(user_action)
            # Add memory
            next_state = state_tracker.get_state(done)
            dqn_agent.add_experience(state, agent_action_index, reward, next_state, done)

        print('Episode: {} Succ.: {} Reward: {}'.format(ep, succ, ep_reward))

        if succ:
            period_succ_total += 1

        if ep % TRAIN_FREQ == 0:
            # Check succ rate
            succ_rate = period_succ_total / TRAIN_FREQ
            print('Succ. Rate: {} Current Best: {}'.format(succ_rate, max(succ_rate_best, SUCCESS_RATE_THRESHOLD)))
            if succ_rate >= succ_rate_best and succ_rate >= SUCCESS_RATE_THRESHOLD:
                print('NEW BEST: {}'.format(succ_rate))
                # Flush
                dqn_agent.empty_memory()
                succ_rate_best = succ_rate
            period_succ_total = 0
            # Copy
            dqn_agent.copy()
            # Train
            dqn_agent.train()
    print("...Train Ended")


# User sim takes first action
def ep_reset():
    # First reset the state tracker
    state_tracker.reset()
    # Then pick an init user action
    user_action = user_sim.reset()
    # Infuse with error
    user_error_action = emc_0.infuse_error(user_action)
    # And update state tracker
    state_tracker.update_state_user(user_error_action)
    # Finally, reset agent
    dqn_agent.reset()


# def test_run():
#     ep = 0
#     while ep < NUM_EP_TEST:
#         ep_reset()
#         ep += 1
#         ep_step = 0
#         done = False
#         while not done:
#             # Get state tracker state
#             state = state_tracker.get_state()
#             # Agent takes action given state tracker's representation of dialogue
#             _, agent_action = dqn_agent.get_action(state)
#             # Update state tracker with the agent's action
#             round_num = state_tracker.update_state_agent(agent_action)
#             # User sim. takes action given agent action
#             user_action, reward, done, succ = user_sim.step(agent_action, round_num)
#             if not done:
#                 # Infuse error into semantic frame level user sim. action
#                 emc_0.infuse_error(user_action)
#                 # Update state tracker with user sim. action
#             state_tracker.update_state_user(user_action)
#
#             ep_step += 1


def main():
    warmup_run()
    # train_run()


if __name__ == "__main__":
    main()