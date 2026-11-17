"""E01-10测试告知；只能用于合成账号，不能据此接收真实学生。"""

from deermind.abstractions.events import Ref

TEST_NOTICE = Ref(owner="product", type="usage_notice", id="synthetic-account-test", revision=1)
TEST_NOTICE_TEXT = (
    "这是合成账号的功能测试，不是正式学生服务。请勿填写真实姓名、联系方式、"
    "身份证件、学习记录或其他个人资料。系统会保存测试账号、监护核实、使用确认、"
    "登录及密码重置的记录；密码只保存散列，不写入事件或日志。"
    "本轮不调用模型处理这些确认，记录可由获准的管理和维护人员查看。"
    "正式告知和数据保留规则尚未确定，本测试不承诺自动删除。"
    "你可以选择暂不使用；没有本人确认和监护确认，不能进入测试功能。"
)


def assent_source(account_id: str, revision: int) -> Ref:
    """确认对应当前账号、当前条件和固定告知，不接受任意外部确认凭证。"""
    return Ref(owner="product", type="assent_prompt", id=account_id, revision=revision)
