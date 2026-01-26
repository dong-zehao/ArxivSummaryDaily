#!/usr/bin/env python
# -*- coding: utf-8 -*-

import shutil
import argparse
from datetime import datetime, timedelta
import re
from pathlib import Path
import os
import subprocess
import json

class SiteManager:
    """ArXiv摘要网站管理器，处理文件清理、索引和归档页面生成"""
    
    # 默认前置元数据模板
    DEFAULT_FRONT_MATTER = """---
layout: default
title: {title}
---

"""
    
    def __init__(self, data_dir, github_dir=None):
        """初始化站点管理器
        
        Args:
            data_dir: 数据目录路径
            github_dir: GitHub配置目录路径
        """
        self.data_dir = Path(data_dir)
        self.github_dir = Path(github_dir) if github_dir else None
        self.data_dir.mkdir(exist_ok=True)  # 确保数据目录存在
    
    def _escape_markdown_chars(self, text):
        """Escapes '|' and '_' characters in markdown text unless already escaped."""
        # Escape '|' that is not already escaped
        text = re.sub(r'(?<!\\)\|', r'\\|', text) # Use r'(?<!\\)\|' to match '|' not preceded by '\'
        # Escape '_' that is not already escaped
        text = re.sub(r'(?<!\\)\_', r'\\_', text) # Use r'(?<!\\)_' to match '_' not preceded by '\'
        return text
    
    def clean_old_files(self, days=30):
        """清理超过指定天数的markdown文件
        
        Args:
            days: 保留文件的最大天数
            
        Returns:
            已删除文件数量
        """
        print(f"清理超过{days}天的旧markdown文件...")
        
        current_time = datetime.now()
        max_age = timedelta(days=days)
        
        # 查找所有摘要文件
        summary_files = list(self.data_dir.glob("summary_*.md"))
        removed_count = 0
        
        for file_path in summary_files:
            # 优先使用文件名中的时间戳，避免检出时修改时间导致的误判
            file_datetime = self._get_summary_datetime(file_path)
            age = current_time - file_datetime

            # 如果文件超过指定天数，删除它
            if age >= max_age:
                file_date = file_datetime.strftime('%Y-%m-%d %H:%M:%S')
                print(f"删除旧文件: {file_path} ({file_date})")
                file_path.unlink()
                removed_count += 1
        
        print(f"清理完成，共删除{removed_count}个文件")
        return removed_count

    def _get_summary_datetime(self, file_path):
        """从文件名中解析摘要时间戳，失败则回退到文件修改时间"""
        match = re.search(r'summary_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', file_path.name)
        if match:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second)
        return datetime.fromtimestamp(file_path.stat().st_mtime)
    
    def get_sorted_summary_files(self):
        """获取按时间排序的摘要文件列表（最新在前）
        
        Returns:
            排序后的文件路径列表
        """
        summary_files = list(self.data_dir.glob("summary_*.md"))
        
        # 按照修改时间排序文件（最新的在前）
        if summary_files:
            summary_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        return summary_files
    
    def extract_content(self, file_path):
        """从文件中提取内容，移除可能存在的前置元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            (title, content) 元组，分别是标题和正文内容
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除前置元数据（如果存在）
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        
        # 提取标题
        title_match = re.search(r'^# (.*?)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else "ArXiv Summary Daily"
        
        return title, content
    
    def copy_latest_to_index(self, sorted_files=None):
        """将所有摘要组合到index.md
        
        Args:
            sorted_files: 可选的已排序文件列表
            
        Returns:
            成功返回True
        """
        if sorted_files is None:
            sorted_files = self.get_sorted_summary_files()
        
        index_path = self.data_dir / "index.md"
        today = datetime.now().strftime('%Y-%m-%d')
        
        if sorted_files:
            print(f"找到 {len(sorted_files)} 个摘要文件，正在组合到index.md...")
            combined_content = self._build_combined_summary_content(sorted_files)
            
            # 添加归档链接
            archive_link = f"[查看所有摘要归档](archive.md) | 更新日期: {today}\n\n"
            archive_data = self._build_archive_data(sorted_files)
            archive_payload = f'<script type="application/json" id="summary-archive-data">{archive_data}</script>\n\n'
            
            # 生成完整内容
            full_content = (
                self.DEFAULT_FRONT_MATTER.format(title="ArXiv Summary Daily")
                + archive_link
                + archive_payload
                + combined_content
            )
            
            # 写入文件
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
                
            print("index.md更新成功")
        else:
            # 如果没有找到文件，创建一个简单的index.md
            print("未找到摘要文件，创建空的index.md")
            default_content = "[查看所有摘要归档](archive.md)\n\n# ArXiv Summary Daily\n\nNo summaries available yet.\n"
            full_content = self.DEFAULT_FRONT_MATTER.format(title="ArXiv Summary Daily") + default_content
            
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
        
        return True

    def _build_combined_summary_content(self, sorted_files):
        """组合所有摘要文件的内容用于首页展示"""
        combined_sections = ["# ArXiv Summary Daily\n"]

        for file_path in sorted_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            escaped_content = self._escape_markdown_chars(content)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(escaped_content)

            title, summary_content = self.extract_content(file_path)
            summary_content = self._strip_primary_heading(summary_content)
            file_date = self._get_summary_datetime(file_path).strftime('%Y-%m-%d')
            summary_header = f"## {file_date} 摘要\n\n[查看该日摘要文件]({file_path.name})\n\n"
            combined_sections.append(summary_header + summary_content + "\n\n---\n\n")

        return "".join(combined_sections).rstrip() + "\n"

    def _strip_primary_heading(self, content):
        """去除摘要内容中的顶层标题，避免首页重复显示"""
        cleaned = content.lstrip()
        return re.sub(r'^# .*\n+', '', cleaned, count=1)
    
    def create_archive_page(self, sorted_files=None):
        """创建归档页面，允许访问所有摘要
        
        Args:
            sorted_files: 可选的已排序文件列表
            
        Returns:
            成功返回True
        """
        if sorted_files is None:
            sorted_files = self.get_sorted_summary_files()
        
        archive_path = self.data_dir / "archive.md"
        print(f"创建归档页面: {archive_path}")
        
        # 准备内容
        header = "[返回首页](index.md)\n\n# ArXiv 摘要归档\n\n以下是所有可用的ArXiv摘要文件，按日期排序（最新在前）：\n\n"
        archive_data = self._build_archive_data(sorted_files)
        archive_payload = f'<script type="application/json" id="summary-archive-data">{archive_data}</script>\n\n'
        content = self.DEFAULT_FRONT_MATTER.format(title="ArXiv Summary 归档") + header + archive_payload
        
        # 处理每个文件，同时确保他们都有前置元数据
        for file_path in sorted_files:
            filename = file_path.name
            # 从文件名中提取日期部分 (格式: summary_YYYYMMDD_HHMMSS.md)
            match = re.search(r'summary_(\d{4})(\d{2})(\d{2})_', filename)
            if match:
                year, month, day = match.groups()
                formatted_date = f"{year}-{month}-{day}"
                
                # 确保摘要文件有前置元数据
                self.ensure_file_has_front_matter(file_path, f"{formatted_date} ArXiv 摘要")
                
                # 添加链接到归档页面
                content += f'- [{formatted_date} 摘要]({filename})\n'
        
        # 写入文件
        with open(archive_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("归档页面创建成功")
        return True

    def _build_archive_data(self, sorted_files):
        """构建前端筛选用的归档JSON数据"""
        archive_entries = []
        for file_path in sorted_files:
            file_datetime = self._get_summary_datetime(file_path)
            archive_entries.append({
                "filename": file_path.name,
                "date": file_datetime.strftime('%Y-%m-%d'),
                "timestamp": file_datetime.isoformat()
            })
        return json.dumps(archive_entries, ensure_ascii=False)
    
    def ensure_file_has_front_matter(self, file_path, title):
        """确保文件有Jekyll前置元数据，没有则添加
        
        Args:
            file_path: 文件路径
            title: 文件标题
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 如果已经有front matter，不做修改
        if content.startswith('---'):
            return
        
        # 添加front matter
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.DEFAULT_FRONT_MATTER.format(title=title) + content)
    
    def setup_site_structure(self):
        """设置Jekyll部署环境，直接部署index.md，不使用导航栏
        
        Returns:
            成功返回True
        """
        if not self.github_dir:
            print("未提供GitHub配置目录，跳过网站结构设置")
            return False
            
        # 1. 复制配置文件
        config_src = self.github_dir / "_config.yml"
        config_dest = self.data_dir / "_config.yml"
        
        if config_src.exists():
            shutil.copy2(config_src, config_dest)
        
        # 2. 创建简单的Gemfile以支持GitHub Pages
        gemfile_path = self.data_dir / "Gemfile"
        gemfile_content = 'source "https://rubygems.org"\ngem "github-pages", group: :jekyll_plugins\ngem "jekyll-theme-cayman"\n'
        with open(gemfile_path, 'w', encoding='utf-8') as f:
            f.write(gemfile_content)
        
        # 3. 确保index.md有正确的前置元数据
        index_path = self.data_dir / "index.md"
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 如果没有front matter，添加一个
            if not content.startswith('---'):
                title, main_content = self.extract_content(index_path)
                with open(index_path, 'w', encoding='utf-8') as f:
                    f.write(self.DEFAULT_FRONT_MATTER.format(title=title) + main_content)
        
        # 4. 复制layout配置
        layouts_dir = self.data_dir / "_layouts"
        mathjax_src = self.github_dir / "_layouts" / "default.html"
        if mathjax_src.exists():
            layouts_dir.mkdir(exist_ok=True)
            mathjax_dest = layouts_dir / "default.html"
            shutil.copy2(mathjax_src, mathjax_dest)
        
        # 5. 复制 mathjax.html 文件
        includes_dir = self.data_dir / "_includes"
        includes_src = self.github_dir / "_includes" / "mathjax.html"
        if includes_src.exists():
            includes_dir.mkdir(exist_ok=True)
            includes_dest = includes_dir / "mathjax.html"
            shutil.copy2(includes_src, includes_dest)
        
        # 6. 复制logo图片
        img_dir = self.data_dir / "img"
        img_dir.mkdir(exist_ok=True)
        
        logo_src = self.github_dir / "img" / "paper.png"
        if logo_src.exists():
            logo_dest = img_dir / "paper.png"
            print(f"复制网站logo: {logo_src} -> {logo_dest}")
            shutil.copy2(logo_src, logo_dest)
        else:
            print(f"警告：未找到logo文件 {logo_src}")
        
        # 7. 删除可能存在的.nojekyll文件，因为我们希望使用Jekyll
        nojekyll_path = self.data_dir / ".nojekyll"
        if nojekyll_path.exists():
            nojekyll_path.unlink()
        
        print("Jekyll部署配置完成 - 直接部署index.md文件")
        return True

def main():
    """主函数，处理命令行参数并执行站点管理任务"""
    parser = argparse.ArgumentParser(description="ArXiv Summary网站管理工具")
    parser.add_argument('--data-dir', default='./data', help='数据目录路径 (默认: ./data)')
    parser.add_argument('--github-dir', default='./.github', help='GitHub配置目录路径 (默认: ./.github)')
    parser.add_argument('--days', type=int, default=30, help='保留摘要文件的天数 (默认: 30)')
    parser.add_argument('--skip-clean', action='store_true', help='跳过清理旧文件')
    args = parser.parse_args()
    
    # 创建站点管理器
    site = SiteManager(args.data_dir, args.github_dir)
    
    # 清理旧文件
    if not args.skip_clean:
        site.clean_old_files(args.days)
    
    # 获取排序后的文件列表（只需获取一次）
    sorted_files = site.get_sorted_summary_files()
    
    # 执行各项任务
    site.copy_latest_to_index(sorted_files)
    site.create_archive_page(sorted_files)
    site.setup_site_structure()
    
    print("所有任务完成！")

if __name__ == "__main__":
    main()
