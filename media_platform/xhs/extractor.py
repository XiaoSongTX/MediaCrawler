# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import json
import re
from typing import Dict, Optional

import humps


class XiaoHongShuExtractor:
    def __init__(self):
        pass

    def extract_note_detail_from_html(self, note_id: str, html: str) -> Optional[Dict]:
        """从html中提取笔记详情

        Args:
            html (str): html字符串

        Returns:
            Dict: 笔记详情字典
        """
        if "noteDetailMap" not in html:
            # 这种情况要么是出了验证码了，要么是笔记不存在
            return None

        state = re.findall(r"window.__INITIAL_STATE__=({.*})</script>", html)[
            0
        ].replace("undefined", '""')
        if state != "{}":
            note_dict = humps.decamelize(json.loads(state))
            return note_dict["note"]["note_detail_map"][note_id]["note"]
        return None

    def extract_creator_info_from_html(self, html: str) -> Optional[Dict]:
        """从html中提取用户信息

        Args:
            html (str): html字符串

        Returns:
            Dict: 用户信息字典
        """
        match = re.search(
            r"<script>window.__INITIAL_STATE__=(.+)<\/script>", html, re.M
        )
        if match is None:
            return None
        info = json.loads(match.group(1).replace(":undefined", ":null"), strict=False)
        if info is None:
            return None
        user_info = info.get("user").get("userPageData")

        # 尝试从HTML中提取IP归属地信息
        ip_location = self._extract_ip_location_from_html(html)
        if user_info and ip_location:
            user_info["ip_location"] = ip_location

        return user_info

    def _extract_ip_location_from_html(self, html: str) -> Optional[str]:
        """从HTML中提取IP归属地信息

        Args:
            html (str): 页面HTML内容

        Returns:
            Optional[str]: IP归属地信息
        """
        # 尝试从页面中提取IP归属地信息
        # 小红书的IP归属地通常在个人资料区域显示
        ip_location_patterns = [
            r'IP属地(?:[:：]\s*)(.+?)<',
            r'IP属地(?:[:：]\s*)(.+?)[\s<]',
            r'IP属地["\s:：]+([^"<>\s]+)',
        ]

        for pattern in ip_location_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # 过滤掉一些无用的信息
                if location and not location.startswith('<') and len(location) <= 20:
                    return location

        return None
