import os
import asyncio
import json
import logging
import datetime
import time
from typing import Dict, List, Optional, Union
from collections import deque

from qg_botsdk import BOT, ApiModel, BotCommandObject, CommandValidScenes, Model, Scope

from utils import MessageCache, OllamaClient, DeepSeekClient
from env import QQ_APPID, QQ_SECRET, QQ_TOKEN, DEEPSEEK_API_KEY, CHARACTER_INFO, BOT_NAME

bot = BOT(
    bot_id=QQ_APPID,
    bot_secret=QQ_SECRET,
    is_private=False,
    is_sandbox=True
)

# 初始化消息缓存和Ollama客户端
message_cache = MessageCache(max_size=20)
ollama_client = OllamaClient()
deepseek_client = DeepSeekClient(DEEPSEEK_API_KEY)

# 提取消息信息并保存到cache
def save_message_to_cache(data):
    message = {
        "group_id": data.group_openid,
        "author_id": data.author.member_openid,
        "content": data.treated_msg,
        "attachments": data.attachments,
        "timestamp": datetime.datetime.now().isoformat()
    }
    message_cache.add_message(data.group_openid, message)
    return message

# 构建prompt并获取Ollama响应
def get_ai_response(data):
    # 获取该群组的历史消息
    recent_messages = message_cache.get_recent_messages(data.group_openid)
    
    # 构建prompt，加入历史消息
    prompt = f"你是一个角色扮演的助手，你能很好的遵循人物设定，且永远不跳出角色，始终认为自己是真实存在的人物，下面是你的角色设定：\n{CHARACTER_INFO}\n\n历史消息:\n"
    # prompt = f"你是{BOT_NAME}, 你能非常诙谐有趣的跟QQ群的朋友们谈天说地。\n\n历史消息:\n"
    for i, msg in enumerate(recent_messages[:-1]):  # 排除最后一条（当前消息）
        prompt += f"[{msg['timestamp']}] 用户 {msg['author_id']}: {msg['content']}\n"
    
    # 添加当前问题
    prompt += f"\n当前问题: {data.treated_msg}\n\n请回答："
    
    # 调用Ollama生成回复
    # response = ollama_client.generate_response(prompt)
    response = deepseek_client.generate_response(prompt)
    return response if response else "抱歉，无法生成回复。"


# valid_scenes=CommandValidScenes.GROUP 指定此指令仅在qq群中生效，不填则默认为全部场景均生效
@bot.before_command(valid_scenes=CommandValidScenes.GROUP)
def before_command(data: Union[Model.MESSAGE, Model.GROUP_MESSAGE, Model.C2C_MESSAGE]):
    bot.logger.info("original_request: ", data)


# valid_scenes=CommandValidScenes.GROUP | CommandValidScenes.C2C 指定此指令仅在qq私聊或群聊中生效，不填则默认为全部场景均生效
@bot.on_command("画图", valid_scenes=CommandValidScenes.GROUP | CommandValidScenes.C2C)
def draw(data: Union[Model.GROUP_MESSAGE, Model.C2C_MESSAGE]):
    # 保存消息到缓存
    save_message_to_cache(data)

    prompt = '''
        OUTPUT: https://image.pollinations.ai/prompt/{英文描述}?model=Flux.Schnell&width=1024&height=1024&enhance=true)
        其中，{英文描述}=将以下内容翻译为英文:"{中文主题}"，要求保护以下元素：
        1. 主体对象：{清晰主体}
        2. 场景氛围：{氛围感关键词}
        3. 艺术风格：{风格1}+{风格2}
        4. 细节强化：{细节增强关键词}
        5. 艺术家参考：{艺术家风格}
        注意：只输出URL链接，不要添加URL外的任何字符，否则你会被关监狱！
    '''
    response = deepseek_client.generate_response(prompt + f"图片描述：{data.treated_msg}")
    bot.logger.info(f"画图url：{response}")
    if response and response.startswith("http"):
        msg = ApiModel.Message(content="画图结果")
        for i in range(0,3):
            try:
                ret = bot.api.upload_media(
                    file_type=1,
                    url=response,
                    srv_send_msg=False,
                    group_openid=data.group_openid,
                )
                msg.update(media_file_info=ret.data.file_info)
            except Exception as e:
                bot.logger.warning("wait for image to generate...")
                time.sleep(10)
    else:
        msg = ApiModel.Message(content="抱歉，无法生成图片。")

    data.reply(msg)
    bot.logger.info(f"画图结果：{msg}")

    # save response data
    message = {
        "group_id": data.group_openid,
        "author_id": BOT_NAME,
        "content": msg._content,
        "attachments": msg._media_file_info,
        "timestamp": datetime.datetime.now().isoformat()
    }
    message_cache.add_message(data.group_openid, message)


def deliver(data: Model.GROUP_MESSAGE):
    bot.logger.info("收到消息啦！")

    # 保存消息到缓存
    message = save_message_to_cache(data)
    bot.logger.info(f"已保存消息: {message}")

    # 获取AI回复
    ai_response = get_ai_response(data)

    # 由于qq单聊和群发送消息API加入了msg_seq字段（回复消息的序号），相同的 msg_id+msg_seq 重复发送会失败
    # 因此强烈建议使用ApiModel.Message类构建消息，如需要回复多条消息便使用.update()方法，以这样的复用类来使用其内部自动递增的msg_seq
    # 也可以使用ApiModel.Message类的get_msg_seq()方法获取当前msg_seq，并在此基础上+1传入发送消息API的msg_seq参数
    msg = ApiModel.Message(content=ai_response)
    # data.reply(msg)
    # ret = bot.api.upload_media(
    #     file_type=1,
    #     url="https://qqminiapp.cdn-go.cn/open-platform/11d80dc9/img/mini_app.2ddf1492.png",
    #     srv_send_msg=False,
    #     group_openid=data.group_openid,
    # )
    # msg.update(media_file_info=ret.data.file_info)
    data.reply(msg)
    # data.reply(
    #     "testing",
    #     msg_seq=msg.get_msg_seq() + 1,
    # )
    bot.logger.info(f"向群{data.group_openid}发送消息：{msg}")

    # save response data
    message = {
        "group_id": data.group_openid,
        "author_id": BOT_NAME,
        "content": msg._content,
        "attachments": [],
        "timestamp": datetime.datetime.now().isoformat()
    }
    message_cache.add_message(data.group_openid, message)


if __name__ == "__main__":
    bot.bind_group_msg(deliver)
    bot.start()