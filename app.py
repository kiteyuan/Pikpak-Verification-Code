from flask import Flask, render_template, request, jsonify
import base64
import poplib
import requests
import re
from email import message_from_bytes

app = Flask(__name__)

# 使用 refresh_token 获取 access_token
def get_access_token(client_id, refresh_token):
    """
    通过 refresh_token 获取新的 access_token
    """
    data = {
        'client_id': client_id,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    response = requests.post('https://login.live.com/oauth20_token.srf', data=data)
    return response.json().get('access_token')

# 使用 access_token 生成 OAuth2 认证字符串
def generate_auth_string(user, token):
    """
    生成用于 POP3 身份验证的 OAuth2 字符串
    """
    auth_string = f"user={user}\1auth=Bearer {token}\1\1"
    return auth_string

# POP3 服务器配置
POP3_SERVER = 'outlook.office365.com'
POP3_PORT = 995  # POP3 SSL 端口

def connect_pop3(email, access_token, verification_senders):
    """
    连接到 POP3 服务器并获取最新的验证码邮件
    """
    try:
        # 连接到 POP3 服务器
        server = poplib.POP3_SSL(POP3_SERVER, POP3_PORT)
        
        # 生成并发送 OAuth2 身份验证字符串
        auth_string = generate_auth_string(email, access_token)
        encoded_auth_string = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        server._shortcmd('AUTH XOAUTH2')
        server._shortcmd(f'{encoded_auth_string}')
        
        # 获取邮件数量
        num_messages = len(server.list()[1])
        verification_code = None
        timestamp = None
        
        # 从最新的邮件开始检查
        for i in range(num_messages, 0, -1):
            response, lines, octets = server.retr(i)
            msg_content = b"\n".join(lines)
            msg = message_from_bytes(msg_content)
            from_email = msg['From']
            
            # 检查发件人是否在验证发件人列表中
            if any(sender in from_email for sender in verification_senders):
                timestamp = msg['Date']
                
                # 获取邮件正文
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/html':
                            body = part.get_payload(decode=True).decode('utf-8')
                            break
                else:
                    body = msg.get_payload(decode=True).decode('utf-8')
                
                # 使用正则表达式提取验证码
                match = re.search(r'<h2>(\d{6})<\/h2>', body)
                if match:
                    verification_code = match.group(1)
                    break
        
        server.quit()
        
        # 返回结果
        if verification_code:
            return {
                "code": 200,
                "verification_code": verification_code,
                "time": timestamp,
                "msg": "成功获取验证码"
            }
        else:
            return {"code": 0, "msg": "未找到验证码"}
    except Exception as e:
        return {"code": 500, "msg": f"错误: {str(e)}"}

@app.route('/')
def index():
    """
    渲染主页
    """
    return render_template('index.html')

@app.route('/get_verification', methods=['POST'])
def get_verification():
    """
    处理获取验证码的请求
    """
    client_id = request.form['client_id']
    email = request.form['email']
    refresh_token = request.form['refresh_token']
    
    verification_senders = ['noreply@accounts.mypikpak.com']
    
    acc_token = get_access_token(client_id, refresh_token)
    result = connect_pop3(email, acc_token, verification_senders)
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
