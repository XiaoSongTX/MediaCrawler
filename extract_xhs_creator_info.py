"""
小红书创作者信息提取脚本
================================

该脚本用于从已爬取的小红书笔记数据中提取创作者（用户）的详细信息，
包括IP归属地等信息，并将这些信息存储到数据库中。

主要功能：
1. 从xhs_note表中提取所有唯一的用户ID
2. 通过HTTP请求获取每个用户的个人主页信息
3. 解析用户主页中的IP归属地等信息
4. 将用户信息存储到xhs_creator表中

使用方法：
1. 确保已经通过项目爬虫爬取了小红书笔记数据（存储在xhs_note表中）
2. 修改脚本中的Cookie信息为有效的登录Cookie
3. 根据数据库配置设置config.SAVE_DATA_OPTION（mysql或sqlite）
4. 在项目根目录下运行脚本：
   uv run python extract_xhs_creator_info.py
   或
   python extract_xhs_creator_info.py

   跳过已存在的创作者（只处理新创作者）：
   uv run python extract_xhs_creator_info.py --skip-exists
   或
   python extract_xhs_creator_info.py --skip-exists

注意事项：
1. 需要有效的登录Cookie才能获取用户信息
2. 脚本会自动处理重复数据（已存在的用户信息会被更新）
3. 为避免被封禁，请求之间添加了延迟
"""
import asyncio
import json
import re
from typing import List, Dict
import config
from database.db_session import get_session
from database.models import XhsNote, XhsCreator
from media_platform.xhs.client import XiaoHongShuClient
from media_platform.xhs.extractor import XiaoHongShuExtractor
from tools import utils
from sqlalchemy import select
import httpx

async def get_xhs_client():
    """创建小红书客户端实例"""
    # TODO 这里需要您提供实际的cookie和headers信息
    cookie_str = ""

    # 将cookie字符串转换为字典
    cookie_dict = {}
    for item in cookie_str.split("; "):
        if "=" in item:
            key, value = item.split("=", 1)
            cookie_dict[key] = value

    xhs_client = XiaoHongShuClient(
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
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.47",
            "Cookie": cookie_str,
        },
        playwright_page=None,
        cookie_dict=cookie_dict,
    )
    return xhs_client

async def extract_user_ids_from_notes() -> List[str]:
    """从xhs_note表中提取所有唯一的user_id"""
    user_ids = set()
    async with get_session() as session:
        stmt = select(XhsNote.user_id)
        result = await session.execute(stmt)
        for row in result:
            if row.user_id:
                user_ids.add(row.user_id)
    return list(user_ids)

async def get_creator_info_from_web(xhs_client: XiaoHongShuClient, user_id: str) -> Dict:
    """通过网页方式获取创作者信息"""
    try:
        # 构建用户主页URL
        url = f"https://www.xiaohongshu.com/user/profile/{user_id}"

        # 使用httpx获取页面内容
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
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
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.47",
                "Cookie": "abRequestId=e98a2ecf-68ee-5495-946c-640bd73a471f; webBuild=4.83.0; a1=19a070892b5502yglmqof0p3uecqhs038m683j1g750000612469; webId=1ff84ea76827bee0e526b9e69747e427; gid=yj08W8YjidYiyj08W8YjJ6VyD228Jvk16AliKkW8Uq7dSY28AxM8qq888KyJ4Kj8D02YqSKj; web_session=0400698e9ce20356d732267acd3a4be300fcce; xsecappid=xhs-pc-web; acw_tc=0a00d5bf17611414583302473eeb0cc1239fa4ee4b134ec2905b5264295c32; websectiga=2845367ec3848418062e761c09db7caf0e8b79d132ccdd1a4f8e64a11d0cac0d; sec_poison_id=752656e0-425f-43a2-998e-9df5523178d8; loadts=1761141566348",
            }
            response = await client.get(url, headers=headers)
            html_content = response.text

        # 使用提取器解析页面内容
        extractor = XiaoHongShuExtractor()
        creator_info = extractor.extract_creator_info_from_html(html_content)

        if creator_info:
            # 提取需要的字段
            basic_info = creator_info.get("basicInfo", {})
            interactions = creator_info.get("interactions", [])
            tag_list = creator_info.get("tags", [])

            # 解析互动信息
            follows = 0
            fans = 0
            interaction_count = 0

            for interaction in interactions:
                if interaction.get("type") == "follows":
                    follows = interaction.get("count", 0)
                elif interaction.get("type") == "fans":
                    fans = interaction.get("count", 0)
                elif interaction.get("type") == "interaction":
                    interaction_count = interaction.get("count", 0)

            return {
                "user_id": user_id,
                "nickname": basic_info.get("nickname", ""),
                "avatar": basic_info.get("images", ""),
                "ip_location": creator_info.get("ip_location", ""),
                "desc": basic_info.get("desc", ""),
                "gender": basic_info.get("gender", ""),
                "follows": follows,
                "fans": fans,
                "interaction": interaction_count,
                "tag_list": tag_list
            }
    except Exception as e:
        utils.logger.error(f"获取用户 {user_id} 信息失败: {e}")
    return {}

async def save_creator_info(creator_info: Dict, skip_exists: bool = False):
    """保存创作者信息到数据库"""
    if not creator_info or not creator_info.get("user_id"):
        return

    async with get_session() as session:
        # 检查是否已存在
        stmt = select(XhsCreator).where(XhsCreator.user_id == creator_info["user_id"])
        result = await session.execute(stmt)
        existing_creator = result.first()

        if existing_creator:
            if skip_exists:
                # 跳过已存在的创作者
                utils.logger.info(f"跳过已存在的创作者: {creator_info.get('nickname', '')} (ID: {creator_info['user_id']})")
                return
            else:
                # 更新现有记录
                existing_creator = existing_creator[0]  # 提取实际对象
                existing_creator.nickname = creator_info.get("nickname", "")
                existing_creator.avatar = creator_info.get("avatar", "")
                existing_creator.ip_location = creator_info.get("ip_location", "")
                existing_creator.desc = creator_info.get("desc", "")
                existing_creator.gender = creator_info.get("gender", "")
                existing_creator.follows = str(creator_info.get("follows", 0))
                existing_creator.fans = str(creator_info.get("fans", 0))
                existing_creator.interaction = str(creator_info.get("interaction", 0))
                existing_creator.tag_list = json.dumps(creator_info.get("tag_list", []))
                existing_creator.last_modify_ts = int(utils.get_current_timestamp())
        else:
            # 创建新记录
            new_creator = XhsCreator(
                user_id=creator_info["user_id"],
                nickname=creator_info.get("nickname", ""),
                avatar=creator_info.get("avatar", ""),
                ip_location=creator_info.get("ip_location", ""),
                add_ts=int(utils.get_current_timestamp()),
                last_modify_ts=int(utils.get_current_timestamp()),
                desc=creator_info.get("desc", ""),
                gender=creator_info.get("gender", ""),
                follows=str(creator_info.get("follows", 0)),
                fans=str(creator_info.get("fans", 0)),
                interaction=str(creator_info.get("interaction", 0)),
                tag_list=json.dumps(creator_info.get("tag_list", []))
            )
            session.add(new_creator)
        await session.commit()

async def main(skip_exists: bool = False):
    """主函数"""
    utils.logger.info(f"开始提取小红书创作者信息... {'(跳过已存在)' if skip_exists else '(更新已存在)'}")

    # 获取小红书客户端
    xhs_client = await get_xhs_client()

    # 从笔记表中提取所有用户ID
    user_ids = await extract_user_ids_from_notes()
    utils.logger.info(f"共找到 {len(user_ids)} 个唯一用户ID")

    # 获取并保存每个创作者的信息
    success_count = 0
    skipped_count = 0
    for i, user_id in enumerate(user_ids):
        # 检查是否已存在（仅在需要跳过时检查）
        if skip_exists:
            async with get_session() as session:
                stmt = select(XhsCreator).where(XhsCreator.user_id == user_id)
                result = await session.execute(stmt)
                existing_creator = result.first()
                if existing_creator:
                    utils.logger.info(f"跳过已存在的创作者: {user_id}")
                    skipped_count += 1
                    continue

        utils.logger.info(f"处理进度: {i+1}/{len(user_ids)}, 当前用户ID: {user_id}")

        # 获取创作者信息
        creator_info = await get_creator_info_from_web(xhs_client, user_id)

        # 保存到数据库
        if creator_info:
            await save_creator_info(creator_info, skip_exists)
            utils.logger.info(f"成功保存用户 {user_id} 的信息，IP归属地: {creator_info.get('ip_location', '未知')}")
            success_count += 1
        else:
            utils.logger.warning(f"未能获取用户 {user_id} 的信息")

        # 添加延迟以避免请求过于频繁
        await asyncio.sleep(2)

    utils.logger.info(f"创作者信息提取完成! 成功处理 {success_count} 个用户，跳过 {skipped_count} 个用户")



# 在 main() 函数末尾添加
if __name__ == "__main__":
    import sys

    # 初始化配置
    config.SAVE_DATA_OPTION = "mysql"  # 或 "sqlite" 根据您的配置

    # 检查命令行参数
    skip_exists = "--skip-exists" in sys.argv

    # 运行主函数
    asyncio.run(main(skip_exists))