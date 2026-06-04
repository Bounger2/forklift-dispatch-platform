def retire_task_temporary_points(task):
    """Hide temporary pickup/dropoff points once their task is closed."""
    retired = []
    for point in (task.origin, task.destination):
        if point and point.is_temporary and point.enabled:
            point.enabled = False
            retired.append(point.id)
    return retired
