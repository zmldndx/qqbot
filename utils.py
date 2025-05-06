import os
import json
import requests
from typing import Dict, List, Optional
from collections import deque

class MessageCache:
    """消息缓存，用于存储每个群的最近消息"""
    def __init__(self, max_size: int = 20, cache_file: str = "message_cache.json"):
        self.max_size = max_size
        self.cache: Dict[str, deque] = {}
        self.cache_file = cache_file
        self.load_cache()
    
    def add_message(self, group_id: str, message: dict):
        """添加消息到缓存"""
        if group_id not in self.cache:
            self.cache[group_id] = deque(maxlen=self.max_size)
        self.cache[group_id].append(message)
        # 每次添加消息后保存缓存
        self.save_cache()
    
    def get_recent_messages(self, group_id: str, count: int = None) -> List[dict]:
        """获取指定群的最近消息"""
        if group_id not in self.cache:
            return []
        
        messages = list(self.cache[group_id])
        if count is not None:
            return messages[-count:]
        return messages
    
    def save_cache(self):
        """保存缓存到文件"""
        try:
            # 将deque转换为列表以便于JSON序列化
            cache_to_save = {group_id: list(messages) for group_id, messages in self.cache.items()}
            with open(self.cache_file, 'w+', encoding='utf-8') as f:
                json.dump(cache_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存消息缓存失败: {str(e)}")
    
    def load_cache(self):
        """从文件加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                
                # 将加载的列表转换回deque
                for group_id, messages in loaded_cache.items():
                    self.cache[group_id] = deque(messages, maxlen=self.max_size)
                print(f"已从 {self.cache_file} 加载消息缓存")
            else:
                print(f"消息缓存文件 {self.cache_file} 不存在，将创建新缓存")
        except Exception as e:
            print(f"加载消息缓存失败: {str(e)}")
            # 如果加载失败，使用空缓存
            self.cache = {}


class OllamaClient:
    """与本地 Ollama 模型通信的客户端"""
    def __init__(self, model_name: str = "qwen2.5:14b", api_base: str = "http://localhost:11434"):
        self.model_name = model_name
        self.api_base = api_base
        self.api_url = f"{api_base}/api/generate"
    
    def generate_response(self, prompt: str) -> Optional[str]:
        """生成回复"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(self.api_url, json=payload)
            if response.status_code == 200:
                result = response.json()
                return result.get("response")
            else:
                print(f"Ollama API 调用失败: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Ollama API 调用出错: {str(e)}")
            return None
        
class DeepSeekClient:
    """与DeepSeek模型API通信的客户端"""
    def __init__(self, api_key: str, model_name: str = "deepseek-chat", api_base: str = "https://api.deepseek.com/v1"):
        self.api_key = api_key
        self.model_name = model_name
        self.api_base = api_base
        self.api_url = f"{api_base}/chat/completions"
    
    def generate_response(self, prompt: str, temperature: float = 0.7, max_tokens: int = 3000) -> Optional[str]:
        """生成回复"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload)
            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content")
            else:
                print(f"DeepSeek API 调用失败: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"DeepSeek API 调用出错: {str(e)}")
            return None