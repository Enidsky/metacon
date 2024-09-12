import akro
from dowel import logger
import os
import numpy as np
from garage import Environment, EnvSpec, EnvStep, StepType
from drl_comunication import DrlComunicationServer
from expirement import MmlinkLimitServer


class MetaConEnv(Environment):
    """A simple 2D point environment.

    Args:
        goal (np.ndarray): A 2D array representing the goal position
        arena_size (float): The size of arena where the point is constrained
            within (-arena_size, arena_size) in each dimension
        done_bonus (float): A numerical bonus added to the reward
            once the point as reached the goal
        never_done (bool): Never send a `done` signal, even if the
            agent achieves the goal
        max_episode_length (int): The maximum steps allowed for an episode.

    """

    def __init__(self, *args, **kwargs):
        print("init: ", args, kwargs)
        self._max_episode_length = kwargs.pop("max_episode_length", 1000)
        self.target_step = kwargs.pop("target_step", 1000)
        self.expirement_id = kwargs.pop("expirement_id", "default")
        self.cur_iter = 0
        self.data_dir = kwargs.pop(
            "data_dir", os.path.join(os.getcwd(), "data", self.expirement_id)
        )
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        self._step_cnt = 0
        # thr, thr_max, avg_delay, min_delay, loss, srtt, cwnd
        self._observation_space = akro.Box(
            np.array([0, 0, 0, 0, 0, 0, 0]),
            np.array(
                [
                    100 * 1000 * 1000 * 8,
                    100 * 1000 * 1000 * 8,
                    100000,
                    100000,
                    1,
                    100000,
                    100000000,
                ]
            ),
        )
        self._action_space = akro.Box(np.array([-0.5]), np.array([0.5]))
        self._spec = EnvSpec(
            action_space=self.action_space,
            observation_space=self.observation_space,
            max_episode_length=self._max_episode_length,
        )
        self.drl_comunication_server = None
        self.mahimhi_limit_server = None
        
    @property
    def action_space(self):
        """akro.Space: The action space specification."""
        return self._action_space

    @property
    def observation_space(self):
        """akro.Space: The observation space specification."""
        return self._observation_space

    @property
    def spec(self):
        """EnvSpec: The environment specification."""
        return self._spec

    @property
    def render_modes(self):
        """list: A list of string representing the supported render modes."""
        return [
            "ascii",
        ]

    def reset(self):
        """Reset the environment.

        Returns:
            numpy.ndarray: The first observation conforming to
                `observation_space`.
            dict: The episode-level information.
                Note that this is not part of `env_info` provided in `step()`.
                It contains information of he entire episode， which could be
                needed to determine the first action (e.g. in the case of
                goal-conditioned or MTRL.)

        """
        if self.drl_comunication_server is not None:
            self.drl_comunication_server.stop_server()
        if self.mahimhi_limit_server is not None:
            self.mahimhi_limit_server.clear()
        self.drl_comunication_server = DrlComunicationServer("/tmp/drl_comunication")
        self.drl_comunication_server.start_server()
        self.cur_iter += 1
        log_dir = os.path.join(self.data_dir, f"{self.cur_iter}")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.mahimhi_limit_server = MmlinkLimitServer(
            "12mbps.trace",
            "12mbps.trace",
            os.path.join(log_dir, "uplink_log_file"),
            os.path.join(log_dir, "downlink_log_file"),
        )
        server_ip = self.mahimhi_limit_server.start_server(12345)
        self.mahimhi_limit_server.start_client(server_ip, 12345)

        # 获取第一次观测值
        obs_msg = self.drl_comunication_server.receive()
        observation = obs_msg.get("observation", [0, 0, 0, 0, 0, 0, 0])

        self._step_cnt = 0
        return observation, {}

    def step(self, action):
        """Step the environment.

        Args:
            action (np.ndarray): An action provided by the agent.

        Returns:
            EnvStep: The environment step resulting from the action.

        Raises:
            RuntimeError: if `step()` is called after the environment
            has been
                constructed and `reset()` has not been called.

        """
        # 执行动作
        self.drl_comunication_server.send({"action": float(action[0])})

        # 获取下一轮观测值
        obs_msg = self.drl_comunication_server.receive()
        # thr, thr_max, avg_delay, min_delay, loss, srtt, cwnd
        observation = obs_msg.get("observation", [0, 0, 0, 0, 0, 0, 0])

        reward = 0
        if observation[1] > 0:
            reward += 10 * (observation[0] / observation[1])
        if observation[2] > 0:
            reward += 1 * (observation[3] / observation[2])
        reward -= 100 * observation[4]

        self._step_cnt += 1
        done = self.target_step == self._step_cnt

        if done:
            reward += 100

        step_type = StepType.get_step_type(
            step_cnt=self._step_cnt,
            max_episode_length=self._max_episode_length,
            done=done,
        )

        if step_type in (StepType.TERMINAL, StepType.TIMEOUT):
            self._step_cnt = None
        
        # self.mahimhi_limit_server.print_client_output()
        # self.mahimhi_limit_server.print_server_output()

        return EnvStep(
            env_spec=self.spec,
            action=action,
            reward=reward,
            env_info={},
            observation=observation,
            step_type=step_type,
        )

    def render(self, mode):
        """Renders the environment.

        Args:
            mode (str): the mode to render with. The string must be present in
                `self.render_modes`.

        Returns:
            str: the point and goal of environment.

        """
        print("render begin")
        return f"Point: {self._point}, Goal: {self._goal}"

    def visualize(self):
        """Creates a visualization of the environment."""
        self._visualize = True
        print(self.render("ascii"))

    def close(self):
        """Close the env."""

    def sample_tasks(self, num_tasks):
        """Sample a list of `num_tasks` tasks.

        Args:
            num_tasks (int): Number of tasks to sample.

        Returns:
            list[dict[str, np.ndarray]]: A list of "tasks", where each task is
                a dictionary containing a single key, "goal", mapping to a
                point in 2D space.

        """
        print("sample_tasks")
        goals = np.random.uniform(-2, 2, size=(num_tasks, 2))
        tasks = [{"goal": goal} for goal in goals]
        return tasks

    def set_task(self, task):
        """Reset with a task.

        Args:
            task (dict[str, np.ndarray]): A task (a dictionary containing a
                single key, "goal", which should be a point in 2D space).

        """
        pass
        # self._task = task
        # self._goal = task["goal"]
