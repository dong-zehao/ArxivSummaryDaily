import os
import sys
import argparse
import json
from datetime import datetime
from .arxiv_client import ArxivClient
from .paper_summarizer import PaperSummarizer
from config.settings import SEARCH_CONFIG, CATEGORIES, QUERY, LLM_CONFIG, OUTPUT_DIR, LAST_RUN_FILE

def main():
    parser = argparse.ArgumentParser(description='ArXiv论文摘要生成工具')
    parser.add_argument('--query', type=str, default=QUERY, help='搜索关键词')
    parser.add_argument('--categories', nargs='+', default=CATEGORIES, help='arXiv分类')
    parser.add_argument('--max-results', type=int, default=SEARCH_CONFIG['max_total_results'], help='获取论文数量')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help='输出目录')
    
    args = parser.parse_args()
    
    # 更新配置
    SEARCH_CONFIG['max_total_results'] = args.max_results
    
    # 初始化客户端
    arxiv_client = ArxivClient(SEARCH_CONFIG)
    paper_summarizer = PaperSummarizer(LLM_CONFIG['api_key'], LLM_CONFIG.get('model'))
    
    # 准备 last_run_file 路径
    last_run_file = os.path.join(args.output_dir, LAST_RUN_FILE)
    
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"开始第 {attempt} 次运行...")
            papers = arxiv_client.search_papers(
                categories=args.categories,
                query=args.query,
                last_run_file=last_run_file
            )
            if not papers:
                print("未找到符合条件的论文")
                return

            # 记录最新文章ID用于在摘要成功后保存
            latest_entry_id = papers[0]['entry_id'] if papers else None

            # 生成摘要
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(args.output_dir, f"summary_{timestamp}.md")

            # 生成摘要并保存
            success = paper_summarizer.summarize_papers(papers, output_file)
            if success:
                print(f"摘要已成功生成并保存到: {output_file}")
            else:
                raise RuntimeError("摘要生成失败，停止此次运行。")

            # 只有在摘要成功生成后才保存最新文章ID
            if latest_entry_id and last_run_file:
                arxiv_client.save_last_run_info(latest_entry_id, last_run_file, len(papers))
                print(f"摘要成功生成，已更新运行记录。下次运行将从最新文章 ID 开始: {latest_entry_id}")
            return
        except Exception as e:
            print(f"运行过程中发生错误: {e}")
            if attempt < max_attempts:
                print("准备重新从头开始运行...")
                continue
            print("已达到最大重试次数，退出且不更新任何内容。")
            sys.exit(1)

if __name__ == '__main__':
    main()
