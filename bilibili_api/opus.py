"""
bilibili_api.opus

图文相关
"""

import enum
import yaml
from typing import Optional
from . import article
from . import dynamic
from .utils.network import Api, Credential
from .utils.utils import get_api, raise_for_statement
from .utils import cache_pool
from .exceptions import ArgsException


API = get_api("opus")


class Opus:
    """
    图文类。

    Attributes:
        credential (Credential): 凭据类
    """

    def __init__(self, opus_id: int, credential: Optional[Credential] = None):
        self.__id = opus_id
        self.__info = None
        self.credential: Credential = credential if credential else Credential()

    def get_opus_id(self) -> int:
        """
        获取图文 id

        Returns:
            int: 图文 idd
        """
        return self.__id

    async def is_article(self) -> bool:
        """
        获取图文是否同时为专栏

        如果是，则专栏/图文/动态数据共享，可以投币

        Returns:
            bool: 是否同时为专栏
        """
        if cache_pool.dynamic_is_article.get(self.__id) is None:
            cache_pool.dynamic_is_article[self.__id] = (await self.get_info())["item"][
                "basic"
            ]["comment_type"] == 12
        return cache_pool.dynamic_is_article[self.__id]

    async def turn_to_article(self) -> "article.Article":
        """
        对专栏图文，转换为专栏（评论、点赞等数据专栏/动态/图文共享）

        如图文无对应专栏将报错。

        Returns:
            article.Article: 专栏类
        """
        # 此处建议先阅读 dynamic.turn_to_article 注释再尝试理解
        if cache_pool.dynamic2article.get(self.__id) is None:
            if not await self.is_article():
                raise ArgsException("提供的动态无对应专栏")
            else:
                cache_pool.dynamic2article[self.__id] = int(
                    (await self.get_info())["item"]["basic"]["rid_str"]
                )
            cache_pool.article2dynamic[cache_pool.dynamic2article[self.__id]] = (
                self.__id
            )
        return article.Article(
            cvid=cache_pool.dynamic2article[self.__id], credential=self.credential
        )

    def turn_to_dynamic(self) -> "dynamic.Dynamic":
        """
        转为动态

        图文完全包含于动态，且图文与专栏 id 数值上一致，因此此函数绝对成功。

        Returns:
            dynamic.Dynamic: 对应的动态类
        """
        return dynamic.Dynamic(dynamic_id=self.__id, credential=self.credential)

    async def get_info(self):
        """
        获取图文基本信息

        Returns:
            dict: 调用 API 返回的结果
        """
        if self.__info is None:
            api = API["info"]["detail"]
            params = {
                "timezone_offset": -480,
                "id": self.__id,
                "features": "onlyfansVote,onlyfansAssetsV2,decorationCard,htmlNewStyle,ugcDelete,editable,opusPrivateVisible",
            }
            self.__info = (
                await Api(**api, credential=self.credential)
                .update_params(**params)
                .result
            )
        if self.__info.get("fallback"):
            raise ArgsException("传入的 opus_id 不正确")
        cache_pool.dynamic_is_opus[self.__id] = True
        return self.__info

    async def markdown(self) -> str:
        """
        将图文转为 markdown

        Returns:
            str: markdown 内容
        """
        await self.get_info()

        title = {"module_title": {"text": ""}}
        content = {"module_content": {"paragraphs": []}}

        for module in self.__info["item"]["modules"]:
            if module.get("module_title"):
                title = module
            if module.get("module_content"):
                content = module

        markdown = f'# {title["module_title"]["text"]}\n\n'

        for para in content["module_content"]["paragraphs"]:
            para_raw = ""
            if para["para_type"] == 1:
                for node in para["text"]["nodes"]:
                    if node.get("rich"):
                        url = node["rich"].get("jump_url")
                        if url is None:
                            url = ""
                        if node["rich"].get("emoji"):
                            url = node["rich"]["emoji"]["icon_url"]
                        text = node["rich"]["text"]
                        if url.startswith("//"):
                            url = "https:" + url
                        if node["rich"].get("emoji"):
                            raw = f"<img width=50px height=50px src={url}> "
                        else:
                            raw = f"[{text}]({url})"
                    elif node.get("word"):
                        raw = node["word"]["words"]
                        if node["word"].get("style"):
                            if node["word"]["style"].get("bold"):
                                if node["word"]["style"]["bold"]:
                                    raw = f"**{raw}**"
                    para_raw += raw + " "
            elif para["para_type"] == 2:
                for pic in para["pic"]["pics"]:
                    url = pic["url"]
                    width = pic["width"]
                    height = pic["height"]
                    para_raw += f"<img width={width} height={height} src={url}> \n"
            markdown += f"{para_raw}\n\n"

        meta_yaml = yaml.safe_dump(self.__info, allow_unicode=True)
        content = f"---\n{meta_yaml}\n---\n\n{markdown}"
        return content
