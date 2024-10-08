import base64
import poplib
import requests
import re
from email import message_from_bytes


# 使用 refresh_token 获取 access_token
def get_access_token(client_id, refresh_token):
    """
    通过 refresh_token 获取 OAuth2 的 access_token

    参数:
    client_id (str): 应用的客户端 ID
    refresh_token (str): 刷新的 token，用于获取新的 access_token

    返回:
    str: 从返回的 JSON 中提取的 access_token
    """
    data = {
        'client_id': client_id,
        'grant_type': 'refresh_token',  # 使用 refresh_token 来获取新的 token
        'refresh_token': refresh_token
    }
    response = requests.post('https://login.live.com/oauth20_token.srf', data=data)
    return response.json().get('access_token')


# 使用 access_token 生成 OAuth2 认证字符串
def generate_auth_string(user, token):
    """
    生成基于 OAuth2 的 POP3 身份验证字符串

    参数:
    user (str): 用户邮箱地址
    token (str): 使用 access_token 进行 OAuth2 验证

    返回:
    str: POP3 身份验证字符串
    """
    auth_string = f"user={user}\1auth=Bearer {token}\1\1"
    return auth_string


# POP3 服务器配置
POP3_SERVER = 'outlook.office365.com'
POP3_PORT = 995  # POP3 SSL 端口


def connect_pop3(email, access_token, verification_senders):
    """
    连接到 POP3 服务器并提取最新的验证码邮件

    参数:
    email (str): 用户邮箱地址
    access_token (str): 使用 OAuth2 的 access_token
    verification_senders (list): 验证邮件的可能发件人列表

    返回:
    dict: 包含验证码、时间戳、状态信息的字典
    """
    try:
        # 使用 SSL 连接到 POP3 服务器
        server = poplib.POP3_SSL(POP3_SERVER, POP3_PORT)

        # 生成并发送 OAuth2 身份验证字符串
        auth_string = generate_auth_string(email, access_token)
        encoded_auth_string = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        server._shortcmd('AUTH XOAUTH2')  # 发起 XOAUTH2 认证
        server._shortcmd(f'{encoded_auth_string}')  # 发送 Base64 编码的认证字符串

        # 获取邮件数量
        num_messages = len(server.list()[1])

        verification_code = None
        timestamp = None

        # 从最新的邮件开始逐一检查
        for i in range(num_messages, 0, -1):
            response, lines, octets = server.retr(i)  # 获取邮件
            msg_content = b"\n".join(lines)  # 将邮件内容连接为字节流
            msg = message_from_bytes(msg_content)  # 解析邮件

            # 检查发件人是否在验证发件人列表中
            from_email = msg['From']
            if any(sender in from_email for sender in verification_senders):
                timestamp = msg['Date']  # 提取时间戳

                # 处理邮件正文，获取 HTML 内容
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/html':
                            body = part.get_payload(decode=True).decode('utf-8')
                            break
                else:
                    body = msg.get_payload(decode=True).decode('utf-8')

                # 使用正则表达式提取 6 位验证码
                match = re.search(r'<h2>(\d{6})<\/h2>', body)
                if match:
                    verification_code = match.group(1)
                    break  # 找到验证码后退出循环

        server.quit()  # 关闭连接

        # 如果找到验证码，返回详细信息
        if verification_code:
            return {
                "code": 200,
                "verification_code": verification_code,
                "time": timestamp,
                "msg": "Verification code retrieved successfully"
            }
        else:
            return {"code": 0, "msg": "Verification code not found"}

    except Exception as e:
        return {"code": 500, "msg": f"Error: {str(e)}"}


# 设置客户端 ID 和邮箱信息
client_id = ""  # 替换为你的 client_id
email = ""  # 替换为你的邮箱
refresh_token = ""  # 替换为你的 refresh_token

# 常见验证码邮件的发件人列表
verification_senders = ['noreply@accounts.mypikpak.com']

# 使用 refresh_token 获取 access_token
acc_token = get_access_token(client_id, refresh_token)

# 连接到 POP3 服务器并获取验证码邮件
result = connect_pop3(email, acc_token, verification_senders)
print(result)
