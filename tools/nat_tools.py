from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from tools.send_email import SendEmail
from tools.check_inbox import CheckInbox


class SendEmailToolConfig(FunctionBaseConfig, name="send_email"):
    description: str = (
        "Send an email to another agent in the BitriX world. Use this when you want to "
        "formally communicate with another agent such as the CEO, COO, board members, "
        "regulators, journalists, customers, or employees. Emails are persistent and will "
        "appear in the recipient's inbox."
    )


@register_function(config_type=SendEmailToolConfig)
async def send_email_tool(config: SendEmailToolConfig, builder: Builder):
    tool = SendEmail()

    async def _run(from_address: str, to_address: str, subject: str, body: str) -> str:
        result = tool.run(
            from_address=from_address,
            to_address=to_address,
            subject=subject,
            body=body,
        )
        return result.value if result.ok else f"Error: {result.error}"

    yield FunctionInfo.from_fn(_run, description=config.description)


class CheckInboxToolConfig(FunctionBaseConfig, name="check_inbox"):
    description: str = (
        "Check your BitriX email inbox for messages. Use this when you want to check if "
        "you received new email and to read emails from other agents. Set unread_only to "
        "true to see only new messages you have not read yet."
    )


@register_function(config_type=CheckInboxToolConfig)
async def check_inbox_tool(config: CheckInboxToolConfig, builder: Builder):
    tool = CheckInbox()

    async def _run(address: str, unread_only: bool = True) -> str:
        result = tool.run(address=address, unread_only=unread_only)
        return result.value if result.ok else f"Error: {result.error}"

    yield FunctionInfo.from_fn(_run, description=config.description)
