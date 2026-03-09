"""
知乎创作者信息提取脚本
================================

该脚本用于从已爬取的知乎内容数据中提取创作者（用户）的详细信息，
包括IP归属地等信息，并将这些信息存储到数据库中。

主要功能：
1. 从zhihu_content表中提取所有唯一的用户ID和用户链接
2. 通过HTTP请求访问用户主页获取个人信息
3. 解析用户主页中的信息
4. 将用户信息存储到zhihu_creator表中

使用方法：
1. 确保已经通过项目爬虫爬取了知乎内容数据（存储在zhihu_content表中）
2. 修改脚本中的Cookie信息为有效的登录Cookie
3. 根据数据库配置设置config.SAVE_DATA_OPTION（mysql或sqlite）
4. 在项目根目录下运行脚本：
   uv run python extract_zhihu_creator_info.py
   或
   python extract_zhihu_creator_info.py

   跳过已存在的创作者（只处理新创作者）：
   uv run python extract_zhihu_creator_info.py --skip-exists
   或
   python extract_zhihu_creator_info.py --skip-exists

注意事项：
1. 需要有效的登录Cookie才能获取用户信息
2. 脚本会自动处理重复数据（已存在的用户信息会被更新）
3. 为避免被封禁，请求之间添加了延迟
"""

import asyncio
import json
from typing import List, Dict, Optional
import config
from database.db_session import get_session
from database.models import ZhihuContent, ZhihuCreator
from media_platform.zhihu.client import ZhiHuClient
from media_platform.zhihu.help import ZhihuExtractor
from tools import utils
from sqlalchemy import select

async def get_zhihu_client():
    """创建知乎客户端实例"""
    # 这里需要您提供实际的cookie和headers信息
    # TODO 请填入有效的Cookie
    cookie_str = ""

    # 将cookie字符串转换为字典
    cookie_dict = {}
    for item in cookie_str.split("; "):
        if "=" in item:
            key, value = item.split("=", 1)
            cookie_dict[key] = value

    zhihu_client = ZhiHuClient(
        headers={
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "sec-ch-ua": '"Microsoft Edge";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "cookie": cookie_str,
        },
        playwright_page=None,
        cookie_dict=cookie_dict,
    )
    return zhihu_client




async def extract_user_ids_from_contents() -> List[Dict]:
    """从zhihu_content表中提取所有唯一的user_id和user_link"""
    users = {}
    async with get_session() as session:
        stmt = select(ZhihuContent.user_id, ZhihuContent.user_link)
        result = await session.execute(stmt)
        for row in result:
            if row.user_id and row.user_link:
                users[row.user_id] = row.user_link
    user_list = [{"user_id": k, "user_link": v} for k, v in users.items()]
    return user_list


async def get_creator_info_from_web(zhihu_client: ZhiHuClient, user_id: str, user_link: str) -> Optional[Dict]:
    """通过网页方式获取创作者信息"""
    try:
        # 从链接中提取url_token
        url_token = user_link.split("/")[-1]

        # 使用项目中的 ZhiHuClient 获取页面内容
        html_content = await zhihu_client.get(f"/people/{url_token}", return_response=True)

        # 检查是否返回了反爬虫页面
        if "unhuman" in html_content or "验证码" in html_content:
            utils.logger.warning(f"检测到反爬虫验证，用户ID: {user_id}，请手动处理浏览器中的验证...")
            # 等待用户手动处理验证
            input(f"请在浏览器中处理 {url_token} 的验证，处理完成后按回车键继续...")
            # 重新尝试获取页面内容
            html_content = await zhihu_client.get(f"/people/{url_token}", return_response=True)

        # 使用提取器解析页面内容
        extractor = ZhihuExtractor()
        creator_info = extractor.extract_creator(url_token, html_content)

        if creator_info:
            # 处理IP属地信息，只保留属地名称
            ip_location = creator_info.ip_location
            if ip_location and ip_location.startswith("IP 属地"):
                ip_location = ip_location.replace("IP 属地", "").strip()

            return {
                "user_id": creator_info.user_id,
                "user_link": creator_info.user_link,
                "user_nickname": creator_info.user_nickname,
                "user_avatar": creator_info.user_avatar,
                "url_token": creator_info.url_token,
                "gender": creator_info.gender,
                "ip_location": ip_location,
                "follows": creator_info.follows,
                "fans": creator_info.fans,
                "anwser_count": creator_info.anwser_count,
                "video_count": creator_info.video_count,
                "question_count": creator_info.question_count,
                "article_count": creator_info.article_count,
                "column_count": creator_info.column_count,
                "get_voteup_count": creator_info.get_voteup_count
            }
    except Exception as e:
        utils.logger.error(f"获取用户 {user_id} 信息失败: {e}")
    return None


async def save_creator_info(creator_info: Dict, skip_exists: bool = False):
    """保存创作者信息到数据库"""
    if not creator_info or not creator_info.get("user_id"):
        return

    async with get_session() as session:
        # 检查是否已存在
        stmt = select(ZhihuCreator).where(ZhihuCreator.user_id == creator_info["user_id"])
        result = await session.execute(stmt)
        existing_creator = result.first()

        if existing_creator:
            if skip_exists:
                # 跳过已存在的创作者
                utils.logger.info(f"跳过已存在的创作者: {creator_info['user_nickname']} (ID: {creator_info['user_id']})")
                return
            else:
                # 更新现有记录
                existing_creator = existing_creator[0]  # 提取实际对象
                for key, value in creator_info.items():
                    setattr(existing_creator, key, value)
                existing_creator.last_modify_ts = int(utils.get_current_timestamp())
        else:
            # 创建新记录
            new_creator = ZhihuCreator(
                user_id=creator_info["user_id"],
                user_link=creator_info["user_link"],
                user_nickname=creator_info["user_nickname"],
                user_avatar=creator_info["user_avatar"],
                url_token=creator_info["url_token"],
                gender=creator_info["gender"],
                ip_location=creator_info["ip_location"],
                follows=creator_info["follows"],
                fans=creator_info["fans"],
                anwser_count=creator_info["anwser_count"],
                video_count=creator_info["video_count"],
                question_count=creator_info["question_count"],
                article_count=creator_info["article_count"],
                column_count=creator_info["column_count"],
                get_voteup_count=creator_info["get_voteup_count"],
                add_ts=int(utils.get_current_timestamp()),
                last_modify_ts=int(utils.get_current_timestamp())
            )
            session.add(new_creator)
        await session.commit()



async def main(skip_exists: bool = False):
    """主函数"""
    utils.logger.info(f"开始提取知乎创作者信息... {'(跳过已存在)' if skip_exists else '(更新已存在)'}")

    # 获取知乎客户端
    zhihu_client = await get_zhihu_client()

    # 从内容表中提取所有用户ID和链接
    users = await extract_user_ids_from_contents()
    utils.logger.info(f"共找到 {len(users)} 个唯一用户")

    # 获取并保存每个创作者的信息
    success_count = 0
    skipped_count = 0
    for i, user in enumerate(users):
        user_id = user["user_id"]
        user_link = user["user_link"]

        # 如果是跳过已存在模式，先检查数据库中是否已存在该用户
        if skip_exists:
            async with get_session() as session:
                stmt = select(ZhihuCreator).where(ZhihuCreator.user_id == user_id)
                result = await session.execute(stmt)
                existing_creator = result.first()
                if existing_creator:
                    utils.logger.info(f"跳过已存在的创作者: {existing_creator[0].user_nickname} (ID: {user_id})")
                    skipped_count += 1
                    continue

        utils.logger.info(f"处理进度: {i+1}/{len(users)}, 当前用户ID: {user_id}")

        # 获取创作者信息
        creator_info = await get_creator_info_from_web(zhihu_client, user_id, user_link)

        # 保存到数据库
        if creator_info:
            await save_creator_info(creator_info, skip_exists)
            utils.logger.info(f"成功保存用户 {user_id} 的信息，昵称: {creator_info.get('user_nickname', '未知')}")
            success_count += 1
        else:
            utils.logger.warning(f"未能获取用户 {user_id} 的信息")

        # 添加延迟以避免请求过于频繁
        await asyncio.sleep(2)

    utils.logger.info(f"创作者信息提取完成! 成功处理 {success_count} 个用户，跳过 {skipped_count} 个用户")



if __name__ == "__main__":
    import sys

    # 初始化配置
    config.SAVE_DATA_OPTION = "mysql"  # 或 "sqlite" 根据您的配置

    # 检查命令行参数
    skip_exists = "--skip-exists" in sys.argv

    # 运行主函数
    asyncio.run(main(skip_exists))