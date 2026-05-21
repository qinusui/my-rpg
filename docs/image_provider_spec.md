# 图像生成 Provider 规范

> 如何为破碎之冠接入新的图像生成服务。照着百炼的实现改 API 调用部分，十分钟能接一个新服务。

> **版权提示**：AI 生成图片的版权归属取决于各 API 提供商的条款。百炼 wanx-v1 生成图在阿里云服务协议下使用。将图片贡献到本仓库的共享图库前，请确认你的 provider 允许公开分发生成结果。本地模型（Stable Diffusion WebUI 等）生成的图片通常无此类限制。

---

## 一、接口规范

你必须定义一个名为 `Provider` 的类，继承 `tools/image_gen/base.py` 中的 `ImageGenerator`，并实现以下两个方法：

```python
from pathlib import Path
from typing import Optional
from .base import ImageGenerator


class Provider(ImageGenerator):

    # ── 必须实现 ───────────────────────────────────────────────

    def generate(self, prompt: str,
                 negative: Optional[str] = None,
                 size: Optional[str] = None,
                 style: str = "scene") -> Path:
        """
        生成一张图片并返回本地文件路径。

        Args:
            prompt:   已拼接 style 后缀的场景描述。直接用。
            negative: 负向提示词。为 None 时用你的默认值。
            size:     图片尺寸字符串。为 None 时用你的默认值。
            style:    "scene" | "combat" | "boss" —— 已通过
                      get_style_suffix() 拼入 prompt，此处仅供参考。

        Returns:
            生成图片的本地绝对路径。可以是临时文件——引擎会将
            其复制到最终位置后删除临时文件。

        Raises:
            RuntimeError: 生成失败时抛出，引擎会打印错误并退出。
        """

    def is_available(self) -> bool:
        """
        检查此 Provider 是否可用。

        检查内容（视你的服务而定）：
        - API key 是否已配置
        - 本地服务是否在运行（如 SD WebUI）
        - 必要的 Python 包是否已安装
        - 额度是否充足

        返回 False 时引擎会尝试 fallback provider（如果配置了）。
        """
```

### 可选覆盖

以下方法有默认实现，按需覆盖：

```python
    def get_style_suffix(self, style: str) -> str:
        """返回追加到 prompt 末尾的风格后缀。

        style 取值: "scene" / "combat" / "boss"

        默认返回空字符串。覆盖此方法可以让 DM 用中文 prompt，
        而你的 provider 自动获得对应英文/风格化后缀。
        """

    def get_default_size(self) -> str:
        """返回默认图片尺寸。默认 "1024*1024"。"""

    def get_default_negative(self) -> str:
        """返回默认负向提示词。默认空字符串。"""
```

### 可选：异步路径

如果你的服务是提交→轮询模式（如百炼 wanx、ComfyUI），可**额外**实现 `submit()` 和 `poll()`。引擎通过 duck typing 自动检测——不需要改任何引擎代码。

```python
    def submit(self, prompt, negative=None, size=None, style="scene") -> str:
        """提交异步任务，返回 task_id 字符串。"""

    def poll(self, task_id: str) -> Optional[Path]:
        """检查异步任务。返回 Path 表示完成，None 表示还在跑。

        引擎在每次"继续"间隙调用 poll()，完成后自动注册+写 meta。
        这意味着玩家看到图之前，生成时间被叙事窗口完全覆盖。
        """
```

实现了这两个方法后，`bg_generator.py --submit` 立即返回（后台生成），`--poll` 收图。没实现则 `--submit` 阻塞等生成完。

---

## 二、注册方式

写完 Python 文件后，只需改 `config.json`：

```json
{
  "image_gen": {
    "provider": "my_provider",
    "fallback": "wanx",
    "providers": {
      "my_provider": { "api_key": "sk-..." },
      "wanx":        { "api_key": "" }
    }
  }
}
```

### 约定（严格）

| 约定 | 说明 |
|------|------|
| 文件名 | `tools/image_gen/<provider_name>.py`（如 `sdwebui.py`） |
| 类名 | 必须是 `Provider` |
| 继承 | 必须继承 `ImageGenerator`（`from .base import ImageGenerator`） |
| config key | 与文件名一致（不含 `.py`） |
| config 内容 | `image_gen.providers.<name>` 下的 JSON 对象原样传给 Provider |

引擎启动时动态 import——`config.json` 改一行，provider 切走。不需要改引擎代码。不需要改 `CLAUDE.md`。不需要在 `__init__.py` 注册。

---

## 三、参考实现：百炼 wanx-v1

以下是一个完整、可运行的异步 Provider 实现。逐段注释说明每一步在做什么。

### 完整代码

```python
"""Bailian wanx-v1 image generation provider (Alibaba Cloud)."""
# ↑ 文件: tools/image_gen/wanx.py
# config.json 中: "provider": "wanx"

import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

from .base import ImageGenerator
# ↑ 相对导入 base.py 中的 ImageGenerator 基类

# ── 默认值 ─────────────────────────────────────────────────────
# 你的服务可能有不同的默认尺寸和负向提示词。
# 覆盖 get_default_size() / get_default_negative() 即可。

WANX_DEFAULT_NEGATIVE = "文字, 水印, UI, HUD, 人物, 角色, 人脸, 明亮鲜艳, 卡通, 动漫"
WANX_DEFAULT_SIZE = "1024*1024"

STYLE_SUFFIX = {
    "scene": (
        "暗黑奇幻概念艺术风格，电影级布光，体积光，"
        "氛围感强，低饱和度色调，油画画风，广角定场镜头，"
        "无人物无角色，纯粹环境场景"
    ),
    "combat": (
        "暗黑奇幻概念艺术风格，动态战斗场景，戏剧性侧光，"
        "怪物居于画面焦点，环境作为衬托，低饱和度，"
        "电影级布光，油画画风"
    ),
    "boss": (
        "史诗级暗黑奇幻概念艺术风格，强烈的明暗对比（chiaroscuro），"
        "巨大体量感，压迫性构图，灾难氛围，电影级布光，"
        "低饱和度，油画画风"
    ),
}
# ↑ 风格后缀在你的 provider 里可以完全不同。
# DALL·E 就写英文概念艺术 prompt，
# SD WebUI 就写 Danbooru 风格的 tag 串。
# 引擎不关心内容——它只负责把后缀拼到 prompt 末尾。


# ── API Key 获取（逐级回退） ───────────────────────────────────
# 这是百炼特有的。你的 provider 可以从 config、环境变量、
# 或任何地方读取配置。引擎不干涉。

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(ROOT, "config.json")


def _load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_api_key():
    """逐级回退：image_gen.providers.wanx.api_key
               → services.dashscope_api_key（旧路径兼容）
               → DASHSCOPE_API_KEY 环境变量"""
    cfg = _load_config()
    key = cfg.get("image_gen", {}).get("providers", {}).get("wanx", {}).get("api_key", "").strip()
    if key:
        return key
    key = cfg.get("services", {}).get("dashscope_api_key", "").strip()
    if key:
        return key
    return os.environ.get("DASHSCOPE_API_KEY", "")


# ── Provider 类 ────────────────────────────────────────────────

class Provider(ImageGenerator):
    """百炼 wanx-v1 —— 异步 Provider 的完整参考实现。

    必须实现:   generate() 和 is_available()
    可选实现:   submit() / poll()（通过 duck typing 检测）
    可选覆盖:   get_style_suffix / get_default_size / get_default_negative
    """

    # ── is_available ─────────────────────────────────────────
    # 引擎每次调用 bg_generator.py 时执行。返回 False 则
    # 尝试 fallback provider。

    def is_available(self) -> bool:
        """检查 dashscope 包是否安装 + API key 是否存在。"""
        try:
            import dashscope.aigc.image_synthesis  # noqa: F401
        except ImportError:
            return False
        return bool(_get_api_key())

    # ── 可选覆盖 ─────────────────────────────────────────────

    def get_style_suffix(self, style: str) -> str:
        """返回百炼专用的中文风格后缀。"""
        return STYLE_SUFFIX.get(style, STYLE_SUFFIX["scene"])

    def get_default_size(self) -> str:
        return WANX_DEFAULT_SIZE

    def get_default_negative(self) -> str:
        return WANX_DEFAULT_NEGATIVE

    # ── submit（可选——异步提交） ──────────────────────────────
    # 实现此方法后，bg_generator.py --submit 立即返回。
    # 玩家在叙事推进的同时，图片在后台生成。

    def submit(self, prompt: str, negative: Optional[str] = None,
               size: Optional[str] = None, style: str = "scene") -> str:
        from dashscope.aigc.image_synthesis import ImageSynthesis

        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY not set")

        # 拼接风格后缀
        style_suffix = self.get_style_suffix(style)
        full_prompt = f"{prompt}, {style_suffix}"

        # 调用 API
        response = ImageSynthesis.call(
            model="wanx-v1",
            prompt=full_prompt,
            negative_prompt=negative or WANX_DEFAULT_NEGATIVE,
            n=1,
            size=size or WANX_DEFAULT_SIZE,
            api_key=api_key,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"wanx API returned {response.status_code}: {response.message}"
            )

        # 返回 task_id——引擎将其存入 pending queue
        return response.output.task_id

    # ── poll（可选——异步轮询） ────────────────────────────────
    # 引擎在每次"继续"间隙调用。返回 None = 还在跑，
    # 返回 Path = 完成（引擎接管后续的注册+写 meta）。

    def poll(self, task_id: str) -> Optional[Path]:
        from dashscope.aigc.image_synthesis import ImageSynthesis

        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY not set")

        resp = ImageSynthesis.fetch(task_id, api_key=api_key)
        if resp.status_code != 200:
            raise RuntimeError(f"wanx poll failed: {resp.message}")

        output = resp.output
        task_status = output.task_status

        if task_status == "SUCCEEDED":
            # 下载到临时文件
            image_url = output.results[0].url
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            try:
                req = urllib.request.Request(
                    image_url,
                    headers={"User-Agent": "my-rpg-bg-generator/1.0"}
                )
                with urllib.request.urlopen(req, timeout=60) as src:
                    tmp.write(src.read())
                tmp.close()
                return Path(tmp.name)
            except Exception:
                if os.path.exists(tmp.name):
                    os.unlink(tmp.name)
                raise

        if task_status == "FAILED":
            raise RuntimeError(
                f"wanx task {task_id} failed: {output.message or 'Unknown error'}"
            )

        # PENDING 或 RUNNING
        return None

    # ── generate（必须——阻塞生成） ─────────────────────────────
    # 即使是异步 Provider 也必须实现 generate()。
    # 百炼的实现：submit → 阻塞等 → 下载 → 返回临时路径。

    def generate(self, prompt: str, negative: Optional[str] = None,
                 size: Optional[str] = None, style: str = "scene") -> Path:
        task_id = self.submit(prompt, negative, size, style)

        from dashscope.aigc.image_synthesis import ImageSynthesis
        api_key = _get_api_key()

        result = ImageSynthesis.wait(task_id, api_key=api_key)
        if result.status_code != 200 or result.output.task_status != "SUCCEEDED":
            raise RuntimeError(f"wanx generation failed: {result.output}")

        image_url = result.output.results[0].url
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            req = urllib.request.Request(
                image_url,
                headers={"User-Agent": "my-rpg-bg-generator/1.0"}
            )
            with urllib.request.urlopen(req, timeout=60) as src:
                tmp.write(src.read())
            tmp.close()
            return Path(tmp.name)
        except Exception:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            raise
```

### 关键点

1. **`generate()` 返回临时文件**——不要自己放到 `rules/` 目录下。引擎负责 `_install_image()`（复制到正确位置→删除临时文件→注册到 `backgrounds.json`→写 `.meta.json`）。你在 `generate()`/`poll()` 里只管生成/下载，存到 `tempfile.NamedTemporaryFile` 返回路径就行。

2. **`submit()` 返回 task_id**——引擎会存到 `_pending_tasks.json`。下次 `--poll` 时传入同一个 task_id。

3. **`poll()` 返回 None 或 Path**——None = "还在跑，下次再查"。Path = "图片已就绪"。引擎接管后续的一切（注册、meta、背景切换）。

4. **错误处理**——所有方法失败时抛 `RuntimeError`，引擎会捕获并打印 JSON 错误信息。不要把异常吞掉。

5. **依赖检查写在 `is_available()` 里**——比如 `import dashscope` 失败则返回 False。不要在模块顶层 import（会导致引擎启动就报错，即使用户没用这个 provider）。

---

## 四、同步 Provider 示例（最小实现）

如果你的服务是同步的（一次 HTTP 调用返回图片，如 SD WebUI、DALL·E），只需要实现两个方法：

```python
"""tools/image_gen/sync_example.py —— 最小同步 Provider 模板"""

import base64
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

from .base import ImageGenerator

SYNC_DEFAULT_SIZE = "1024x1024"
SYNC_DEFAULT_NEGATIVE = "text, watermark, low quality"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(ROOT, "config.json")


class Provider(ImageGenerator):
    """同步 Provider 的最小实现模板。"""

    def is_available(self) -> bool:
        # 检查你的服务是否可达
        return True  # 替换为实际检测逻辑

    def get_default_size(self) -> str:
        return SYNC_DEFAULT_SIZE

    def get_default_negative(self) -> str:
        return SYNC_DEFAULT_NEGATIVE

    def generate(self, prompt: str, negative: Optional[str] = None,
                 size: Optional[str] = None, style: str = "scene") -> Path:
        # 1. 构造请求
        payload = json.dumps({
            "prompt": prompt,
            "negative_prompt": negative or SYNC_DEFAULT_NEGATIVE,
        }).encode("utf-8")

        # 2. 调用你的 API
        req = urllib.request.Request(
            "https://your-api.example.com/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # 3. 解码图片数据
        img_data = base64.b64decode(data["image"])
        # 或者直接从 URL 下载——取决于你的 API

        # 4. 写入临时文件，返回路径
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(img_data)
        tmp.close()
        return Path(tmp.name)
```

不实现 `submit()`/`poll()` 时，`bg_generator.py --submit` 阻塞等 `generate()` 完成——玩家短时间等待后看到图。对本地 GPU（2–10 秒生成）完全可接受。
