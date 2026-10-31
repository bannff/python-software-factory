class SchedulerError(ValueError): pass
class ScheduleNotFoundError(SchedulerError): pass
class ScheduleConflictError(SchedulerError): pass

__all__ = ["SchedulerError", "ScheduleNotFoundError", "ScheduleConflictError"]
