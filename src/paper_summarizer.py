"""
论文总结模块 - 使用大语言模型API生成论文摘要
"""
import os
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import requests
import time
from datetime import datetime
import pytz
import html
from config.settings import LLM_CONFIG, CATEGORIES

class ModelClient:
    """语言模型API客户端"""
    
    def __init__(self, api_key: str, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model or LLM_CONFIG['model']
        self.api_url = f"{LLM_CONFIG['api_url']}/{self.model}:generateContent"
        self.timeout = LLM_CONFIG.get('timeout', 30)
        
    def _create_headers(self) -> Dict[str, str]:
        """创建请求头"""
        return {
            "Content-Type": "application/json"
        }
    
    def _create_request_body(
        self, 
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """创建请求体"""
        # 将最后一条消息作为提示词
        prompt = messages[-1]["content"]
        
        return {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": temperature or LLM_CONFIG['temperature'],
                "maxOutputTokens": max_tokens or LLM_CONFIG['max_output_tokens'],
                "topP": LLM_CONFIG['top_p'],
                "topK": LLM_CONFIG['top_k']
            }
        }
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """创建聊天完成"""
        headers = self._create_headers()
        data = self._create_request_body(messages, temperature, max_tokens)
        
        for attempt in range(LLM_CONFIG['retry_count']):
            try:
                response = requests.post(
                    f"{self.api_url}?key={self.api_key}",
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code != 200:
                    raise Exception(f"API 调用失败: {response.text}")
                    
                result = response.json()
                
                return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": result["candidates"][0]["content"]["parts"][0]["text"]
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    }
                }
            except requests.Timeout:
                print(f"请求超时（{self.timeout}秒），正在重试...")
                if attempt == LLM_CONFIG['retry_count'] - 1:
                    raise TimeoutError(f"API调用在{self.timeout}秒内未响应，已重试{LLM_CONFIG['retry_count']}次")
                time.sleep(LLM_CONFIG['retry_delay'] * (2 ** attempt))
            except Exception as e:
                if attempt == LLM_CONFIG['retry_count'] - 1:
                    raise
                time.sleep(LLM_CONFIG['retry_delay'] * (2 ** attempt))

class PaperSummarizer:
    def __init__(self, api_key: str, model: Optional[str] = None):
        self.client = ModelClient(api_key, model)
        self.max_papers_per_batch = 50

    def _generate_batch_summaries(self, papers: List[Dict[str, Any]], start_index: int) -> str:
        """为一批论文生成总结"""
        batch_prompt = ""
        for i, paper in enumerate(papers, start=start_index):
            batch_prompt += f"""
论文 {i}：
标题：{paper['title']}
作者：{', '.join(paper['authors'])}
发布日期：{paper['published'][:10]}
arXiv链接：{paper['entry_id']}
论文摘要：{paper['summary']}

"""
        
        final_prompt = f"""请为以下{len(papers)}篇论文分别生成markdown语言格式的总结。对每篇论文：
1. 用一句话说明研究目的
2. 用一句话说明主要发现
请用中文回答，保持原有格式，对每篇论文的回答后加入markdown格式的"---"分隔符。
确保对每篇论文的编号、标题等信息保持不变。
你的输出环境同时支持markdown和LaTeX语法渲染，可以直接使用LaTeX语法来表示数学公式和符号。请将需要使用LaTeX语法的部分用美元符号$包裹起来，其中若需要下标或上标，请保证将相应的元素用大括号包裹。
输出格式为：

### [标题](文章链接)
- **作者:** (作者)
- **研究目的:** (研究目的)
- **主要发现:** (主要发现)

---

### [标题](文章链接)
- **作者:** (作者)
- **研究目的:** (研究目的)
- **主要发现:** (主要发现)

---

......

---

### [标题](文章链接)
- **作者:** (作者)
- **研究目的:** (研究目的)
- **主要发现:** (主要发现)

---

请注意，以上是对每篇论文的总结格式示例。请确保输出格式与示例一致。

以下是一个示例：

---

### [Lattice models with subsystem/weak non-invertible symmetry-protected topological order](http://arxiv.org/abs/2505.11419v1)
- **作者:** Yuki Furukawa
- **研究目的:** 构建具有子系统非可逆对称性保护拓扑 (SPT) 序的格点模型，并研究其界面模式以及弱SPT相。
- **主要发现:** 构建了一系列具有子系统非可逆SPT序的格点模型，并展示了由平移对称性和非可逆对称性组合区分的弱SPT相之间的界面存在奇异的Lieb-Schultz-Mattis反常。

---

请根据以下论文信息生成总结：
{batch_prompt}"""

        try:
            response = self.client.chat_completion([{
                "role": "user",
                "content": final_prompt
            }])
            return response["choices"][0]["message"]["content"].strip()
        except Exception as e:
            # 如果批处理失败，生成错误信息
            error_summaries = []
            for i, paper in enumerate(papers, start=start_index):
                error_summaries.append(f"""
论文 {i}：
标题：{paper['title']}
作者：{', '.join(paper['authors'])}
发布日期：{paper['published'][:10]}
arXiv链接：{paper['pdf_url']}
研究目的：[生成失败: {str(e)}]
主要发现：[生成失败: {str(e)}]
---""")
            return "\n".join(error_summaries)

    def _process_batch(self, papers: List[Dict[str, Any]], start_index: int) -> str:
        """处理一批论文"""
        print(f"正在批量处理 {len(papers)} 篇论文...")
        summaries = self._generate_batch_summaries(papers, start_index)
        time.sleep(2)  # 在批次之间添加短暂延迟
        return summaries

    def _generate_batch_summary(self, papers: List[Dict[str, Any]]) -> str:
        """批量生成所有论文的总结"""
        all_summaries = []
        total_papers = len(papers)
        
        for i in range(0, total_papers, self.max_papers_per_batch):
            batch = papers[i:i + self.max_papers_per_batch]
            print(f"\n正在处理第 {i + 1} 到 {min(i + self.max_papers_per_batch, total_papers)} 篇论文...")
            batch_summary = self._process_batch(batch, i + 1)
            all_summaries.append(batch_summary)
            
            if i + self.max_papers_per_batch < total_papers:
                print("批次处理完成，等待3秒后继续...")
                time.sleep(3)  # 批次之间的冷却时间
        
        return "\n".join(all_summaries)

    def summarize_papers(self, papers: List[Dict[str, Any]], output_file: str) -> bool:
        """
        批量处理所有论文并创建Markdown报告
        
        Args:
            papers: 论文列表
            output_file: 输出文件路径
            
        Returns:
            bool: 摘要生成是否真正成功。如果生成的摘要包含错误信息则返回False
        """
        api_success = True  # 标记API调用是否成功
        
        try:
            # 生成总结内容
            print(f"开始生成论文总结，共 {len(papers)} 篇...")
            summaries = self._generate_batch_summary(papers)
            
            # 检查生成的摘要是否包含错误信息
            if "[生成失败:" in summaries:
                api_success = False
                print("警告: 摘要生成过程中出现错误，结果可能不完整")
            
            # 转换为markdown格式
            markdown_content = self._generate_markdown(papers, summaries)
            
            # 保存为markdown文件
            output_md = output_file.replace('.pdf', '.md')
            with open(output_md, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print(f"Markdown文件已保存：{output_md}")
            
            return api_success
            
        except Exception as e:
            # 如果生成总结失败，保存基本信息为markdown格式
            beijing_time = datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
            error_content = f"""# Arxiv论文总结报告

生成时间：{beijing_time}

**生成总结时发生错误，以下是论文基本信息：**

"""
            for i, paper in enumerate(papers, 1):
                error_content += f"""
## 论文 {i}：
- 标题：{paper['title']}
- 作者：{', '.join(paper['authors'])}
- 发布日期：{paper['published'][:10]}
- arXiv链接：{paper['pdf_url']}

"""
            
            # 保存错误信息为markdown文件
            error_md = output_file.replace('.pdf', '_error.md')
            with open(error_md, 'w', encoding='utf-8') as f:
                f.write(error_content)
            print(f"发生错误，已保存基本信息到：{error_md}")
            
            return False  # 发生异常，摘要生成肯定失败

    def _generate_markdown(self, papers: List[Dict[str, Any]], summaries: str) -> str:
        """生成markdown格式的报告"""
        beijing_time = datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
        summary_sections = self._split_summary_sections(summaries)
        formatted_summaries = self._format_summary_sections(papers, summary_sections)

        markdown_content = f"""# Arxiv论文总结报告

## 基本信息
- 生成时间：{beijing_time}
- 使用模型：{self.client.model}
- 论文数量：{len(papers)} 篇

---

## 论文总结

{formatted_summaries}

---

## 生成说明
- 本报告由AI模型自动生成
- 每篇论文的总结包含研究目的和主要发现
- 如有错误或遗漏请以原文为准
"""
        return markdown_content

    def _split_summary_sections(self, summaries: str) -> List[str]:
        """将模型输出的摘要按分隔符拆分为单篇条目"""
        if not summaries:
            return []
        cleaned = summaries.strip()
        cleaned = re.sub(r'^\s*---\s*', '', cleaned)
        sections = re.split(r'\n---\s*\n', cleaned)
        return [section.strip() for section in sections if section.strip()]

    def _format_summary_sections(self, papers: List[Dict[str, Any]], sections: List[str]) -> str:
        """将摘要片段与论文元数据拼接为可筛选的HTML块"""
        formatted_blocks = []
        allowed_categories = set(CATEGORIES)
        for index, paper in enumerate(papers):
            section = sections[index] if index < len(sections) else ""
            categories = paper.get('categories') or []
            filtered_categories = [cat for cat in categories if cat in allowed_categories]
            categories_label = ", ".join(filtered_categories) if filtered_categories else "未分类"
            categories_attr = html.escape(",".join(filtered_categories))
            published_date = paper.get('published', '')[:10]
            block = f"""<section class="paper-summary" data-categories="{categories_attr}" data-published="{published_date}" markdown="1">
<div class="paper-summary-meta">
  <span><strong>分类:</strong> {categories_label}</span>
  <span><strong>发布日期:</strong> {published_date}</span>
</div>

{section}
</section>"""
            formatted_blocks.append(block)
        return "\n\n".join(formatted_blocks)
