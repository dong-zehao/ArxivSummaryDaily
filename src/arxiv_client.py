"""
ArXiv API 客户端模块
"""
import arxiv
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from config.settings import SEARCH_CONFIG, QUERY

class ArxivClient:
    def __init__(self, config=None):
        self.client = arxiv.Client()
        self.config = config or SEARCH_CONFIG

    def _safe_get_categories(self, paper: arxiv.Result) -> List[str]:
        """安全地获取论文分类"""
        try:
            if isinstance(paper.categories, (list, tuple, set)):
                return list(paper.categories)
            elif isinstance(paper.categories, str):
                return [paper.categories]
            else:
                return [str(paper.categories)]
        except Exception as e:
            print(f"调试 - 获取分类出错: {e}")
            return [paper.primary_category] if paper.primary_category else []

    def _load_last_run_info(self, last_run_file: str) -> Optional[str]:
        """加载上次运行的最新文章ID"""
        try:
            with open(last_run_file, 'r') as f:
                data = json.load(f)
                return data.get('latest_entry_id')
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def save_last_run_info(self, latest_entry_id: str, last_run_file: str, total_results: int = 0):
        """
        保存本次运行的最新文章ID
        
        Args:
            latest_entry_id: 最新文章的ID
            last_run_file: 存储运行信息的文件路径
            total_results: 本次获取的结果数量
        """
        try:
            os.makedirs(os.path.dirname(last_run_file), exist_ok=True)
            with open(last_run_file, 'w') as f:
                json.dump({
                    'latest_entry_id': latest_entry_id,
                    'timestamp': datetime.now().isoformat(),
                    'total_results': total_results
                }, f, indent=2)
            print(f"已更新运行记录，最新文章 ID: {latest_entry_id}")
        except Exception as e:
            print(f"保存运行记录时出错: {e}")

    def _create_search_query(self, query: str = "", 
                           categories: Optional[List[str]] = None,
                           keywords: Optional[Dict[str, List[str]]] = None) -> str:
        """构建高级搜索查询"""
        search_parts = []
        
        # 添加基本查询
        if query:
            if self.config['title_only']:
                search_parts.append(f"ti:{query}")
            elif self.config['abstract_only']:
                search_parts.append(f"abs:{query}")
            elif self.config['author_only']:
                search_parts.append(f"au:{query}")
            else:
                search_parts.append(query)

        # 添加分类（使用 OR 连接所有分类）
        if categories:
            try:
                cat_parts = []
                for cat in categories:
                    if not cat:
                        continue
                    if self.config['include_cross_listed']:
                        cat_parts.append(f"cat:{cat}")
                    else:
                        cat_parts.append(f"primary_cat:{cat}")
                
                if cat_parts:
                    cat_query = " OR ".join(cat_parts)
                    search_parts.append(f"({cat_query})")
            except Exception as e:
                print(f"调试 - 构建分类查询出错: {e}")

        final_query = " AND ".join(search_parts) if search_parts else "*:*"
        return final_query

    def search_papers(self, 
                     categories: Optional[List[str]] = None,
                     query: str = QUERY,
                     last_run_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        搜索论文并返回元数据，支持多个分类的查询和去重
        
        Args:
            categories: arXiv分类列表
            query: 搜索关键词
            last_run_file: 存储上次运行信息的文件路径（可选）
        """
        all_results = []
        
        # 加载上次运行的最新文章ID
        last_entry_id = None
        if last_run_file and os.path.exists(last_run_file):
            last_entry_id = self._load_last_run_info(last_run_file)
            if last_entry_id:
                print(f"找到上次运行记录，将从文章 ID: {last_entry_id} 开始检索新论文")
            else:
                print(f"找到上次运行记录文件，但无法获取有效的entry_id")
        
        # 构建查询
        search_query = self._create_search_query(query, categories)
        print(f"使用查询: {search_query}")
        
        # 设置排序标准
        sort_criterion = getattr(arxiv.SortCriterion, self.config['sort_by'])
        sort_order = getattr(arxiv.SortOrder, self.config['sort_order'])
        
        try:
            # 创建搜索参数字典
            search_kwargs = {
                'query': search_query,
                'max_results': self.config['max_total_results'],
                'sort_by': sort_criterion,
                'sort_order': sort_order
            }
            
            # 只在 id_list 不为 None 时添加到参数中
            if self.config['id_list'] is not None:
                search_kwargs['id_list'] = self.config['id_list']
            
            search = arxiv.Search(**search_kwargs)
            latest_entry_id = None

            for paper in self.client.results(search):
                try:
                    # 如果是第一篇文章，记录其ID
                    if not latest_entry_id:
                        latest_entry_id = paper.entry_id

                    # 如果遇到上次处理过的文章，就停止查询
                    if last_entry_id and paper.entry_id == last_entry_id:
                        print(f"遇到上次处理过的文章（ID: {last_entry_id}），停止检索")
                        break

                    metadata = {
                        'title': paper.title,
                        'authors': [author.name for author in paper.authors],
                        'published': paper.published.isoformat(),
                        'updated': paper.updated.isoformat(),
                        'summary': paper.summary,
                        'doi': paper.doi,
                        'primary_category': paper.primary_category,
                        'categories': self._safe_get_categories(paper),
                        'links': [link.href for link in paper.links],
                        'pdf_url': paper.pdf_url,
                        'entry_id': paper.entry_id,
                        'comment': getattr(paper, 'comment', '')
                    }
                    all_results.append(metadata)
                    
                except Exception as e:
                    raise RuntimeError(f"处理单篇文章时出错: {e}") from e
                
        except Exception as e:
            print(f"搜索过程出错: {e}")
            print(f"错误类型: {type(e)}")
            import traceback
            print(f"错误堆栈: {traceback.format_exc()}")
            raise

        if not all_results:
            print("未找到新的论文")
        else:
            print(f"找到 {len(all_results)} 篇新论文")

        return all_results
