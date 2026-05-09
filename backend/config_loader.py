# 配置文件加载模块
import configparser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.ini"

_config = None

def load_config():
    """加载配置文件"""
    global _config
    if _config is None:
        _config = configparser.ConfigParser()
        if CONFIG_PATH.exists():
            _config.read(CONFIG_PATH, encoding='utf-8')
        else:
            # 默认配置
            _config['server'] = {
                'host': '0.0.0.0',
                'port': '8000',
                'frontend_url': 'http://localhost:8000'
            }
    return _config

def get_server_url():
    """获取服务器URL"""
    config = load_config()
    host = config.get('server', 'host', fallback='0.0.0.0')
    port = config.get('server', 'port', fallback='8000')
    # 如果host是0.0.0.0，使用127.0.0.1作为默认值
    if host == '0.0.0.0':
        host = 'localhost'
    return f"http://{host}:{port}"

def get_frontend_url():
    """获取前端URL"""
    config = load_config()
    return config.get('server', 'frontend_url', fallback='http://localhost:8000')
