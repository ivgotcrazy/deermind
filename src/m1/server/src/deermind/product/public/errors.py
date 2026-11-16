"""普通写命令的公开冲突错误，不暴露存储实现。"""


class RequestConflict(ValueError):
    """同一请求身份携带不同输入，不能当作技术重试。"""
