Tune Internals
==============

.. _raytrialexecutor-docstring:

TunerInternal
---------------

.. autoclass:: ray.tune.impl.tuner_internal.TunerInternal
    :members:


.. _trial-docstring:

Trial
-----

.. autoclass:: ray.tune.experiment.trial.Trial
    :members:

FunctionTrainable
-----------------

.. autoclass:: ray.tune.trainable.function_trainable.FunctionTrainable

.. autofunction:: ray.tune.trainable.function_trainable.wrap_function


Registry
--------

.. autofunction:: ray.tune.register_trainable

.. autofunction:: ray.tune.register_env


Output
------

.. autoclass:: ray.tune.experimental.output.ProgressReporter
.. autoclass:: ray.tune.experimental.output.TrainReporter
.. autoclass:: ray.tune.experimental.output.TuneReporterBase
.. autoclass:: ray.tune.experimental.output.TuneTerminalReporter
