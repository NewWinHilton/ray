import logging
from typing import Optional

import ray
from ray.train.v2._internal.execution.callback import (
    ControllerCallback,
    WorkerGroupCallback,
)
from ray.train.v2._internal.execution.context import TrainRunContext
from ray.train.v2._internal.execution.controller.state import (
    AbortedState,
    ErroredState,
    FinishedState,
    ResizingState,
    RestartingState,
    RunningState,
    SchedulingState,
    TrainControllerState,
)
from ray.train.v2._internal.execution.scaling_policy.scaling_policy import (
    ResizeDecision,
)
from ray.train.v2._internal.execution.worker_group import (
    WorkerGroup,
    WorkerGroupContext,
    WorkerGroupState,
)
from ray.train.v2._internal.execution.worker_group.poll import WorkerGroupPollStatus
from ray.train.v2._internal.logging.logging import (
    get_train_application_controller_log_path,
)
from ray.train.v2._internal.state.state_manager import TrainStateManager

logger = logging.getLogger(__name__)


class StateManagerCallback(ControllerCallback, WorkerGroupCallback):
    def after_controller_start(self, train_run_context: TrainRunContext):
        self._state_manager = TrainStateManager()
        self._run_name = train_run_context.get_run_config().name
        self._run_id = train_run_context.run_id

        # TODO: Should this be generated by the caller?
        # NOTE: These must be called on the Controller.
        #       The Callback is first initialized on the Driver.
        core_context = ray.runtime_context.get_runtime_context()
        self._job_id = core_context.get_job_id()
        self._controller_actor_id = core_context.get_actor_id()
        controller_log_file_path = get_train_application_controller_log_path()
        self._state_manager.create_train_run(
            id=self._run_id,
            name=self._run_name,
            job_id=self._job_id,
            controller_actor_id=self._controller_actor_id,
            controller_log_file_path=controller_log_file_path,
        )

    def after_controller_state_update(
        self,
        previous_state: TrainControllerState,
        current_state: TrainControllerState,
    ):
        if previous_state._state_type == current_state._state_type:
            return

        logger.info(
            f"[State Transition] {previous_state._state_type.state_name} -> "
            f"{current_state._state_type.state_name}."
        )

        if isinstance(current_state, SchedulingState):
            # TODO: This should probably always be ResizeDecision.
            if isinstance(current_state.scaling_decision, ResizeDecision):
                resize_decision = current_state.scaling_decision
            else:
                resize_decision = None

            self._state_manager.update_train_run_scheduling(
                run_id=self._run_id,
                resize_decision=resize_decision,
            )

        elif isinstance(current_state, RunningState):
            self._state_manager.update_train_run_running(
                run_id=self._run_id,
            )

        elif isinstance(current_state, RestartingState):
            self._state_manager.update_train_run_restarting(
                run_id=self._run_id,
            )

        elif isinstance(current_state, ResizingState):
            self._state_manager.update_train_run_resizing(
                run_id=self._run_id,
            )

        elif isinstance(current_state, ErroredState):
            self._state_manager.update_train_run_errored(
                run_id=self._run_id,
                status_detail=str(current_state.training_failed_error),
            )

        elif isinstance(current_state, FinishedState):
            self._state_manager.update_train_run_finished(
                run_id=self._run_id,
            )

        elif isinstance(current_state, AbortedState):
            self._state_manager.update_train_run_aborted(
                run_id=self._run_id,
            )

    def before_worker_group_start(self, worker_group_context: WorkerGroupContext):
        self._state_manager.create_train_run_attempt(
            run_id=self._run_id,
            attempt_id=worker_group_context.run_attempt_id,
            num_workers=worker_group_context.num_workers,
            resources_per_worker=worker_group_context.resources_per_worker,
        )

    def after_worker_group_start(self, worker_group: WorkerGroup):
        worker_group_context: WorkerGroupContext = (
            worker_group.get_worker_group_context()
        )
        worker_group_state: WorkerGroupState = worker_group.get_worker_group_state()
        self._state_manager.update_train_run_attempt_running(
            run_id=self._run_id,
            attempt_id=worker_group_context.run_attempt_id,
            workers=worker_group_state.workers,
        )

    def before_worker_group_shutdown(self, worker_group: WorkerGroup):
        worker_group_context: WorkerGroupContext = (
            worker_group.get_worker_group_context()
        )
        # TODO: Consider passing error reason directly to the callback.
        # Something along the lines of:
        #    WorkerGroup.shutdown(reason)
        #    -> WorkerGroupCallback.before_worker_group_shutdown(reason)
        worker_group_poll_status: Optional[
            WorkerGroupPollStatus
        ] = worker_group.get_latest_poll_status()
        if worker_group_poll_status and worker_group_poll_status.errors:
            self._state_manager.update_train_run_attempt_errored(
                run_id=self._run_id,
                attempt_id=worker_group_context.run_attempt_id,
                status_detail=worker_group_poll_status.get_error_string(),
            )
        else:
            self._state_manager.update_train_run_attempt_finished(
                run_id=self._run_id,
                attempt_id=worker_group_context.run_attempt_id,
            )

    def before_worker_group_abort(self, worker_group_context: WorkerGroupContext):
        self._state_manager.update_train_run_attempt_aborted(
            self._run_id,
            worker_group_context.run_attempt_id,
        )
