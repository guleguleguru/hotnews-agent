"""
AI 新闻评分器
结构化 JSON 输出 + 确定性分数计算
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
from loguru import logger
from config import config


class NewsScorer:
    """
    AI 新闻评分器
    结构化 JSON 输出 + 确定性分数计算
    """
    
    # 结构化 JSON 评分提示词
    STRUCTURED_SCORE_PROMPT_TEMPLATE = """
You are a cynical, hard-to-impress tech investor. You have seen it all. Most news is hype and PR noise. You are extremely skeptical and DEFAULT TO LOW SCORES. Only give high scores if the event significantly changes the market landscape.

YOUR TASK: Analyze the article and return a JSON object with the following structure:

{{
  "tier": "S|A|B|C",
  "impact": 0-5,
  "novelty": 0-5,
  "credibility": 0-5,
  "actionability": 0-5,
  "flags": {{
    "clickbait": true|false,
    "job_posting": true|false,
    "sports": true|false,
    "tool": true|false,
    "tutorial": true|false,
    "opinion_only": true|false
  }},
  "reasons": ["reason1", "reason2", "reason3"]
}}

TIER DEFINITIONS:
- **S Tier**: Industry-shaking events that fundamentally change markets (only for truly exceptional news, <3% of articles)
- **A Tier**: Major updates with high value and significant impact (<10% of articles)
- **B Tier**: Regular news and information (most articles should be here)
- **C Tier**: Noise, hype, low-value content (default for most articles)

DIMENSION SCORING (0-5):
- **impact**: How wide/deep is the impact? (0=no impact, 5=industry-wide transformation)
- **novelty**: How new/non-repetitive is this? (0=old news, 5=completely new)
- **credibility**: Does it have hard facts? (0=rumor/speculation, 5=verified facts)
- **actionability**: Can it influence decisions? (0=no action needed, 5=must act)

FLAGS:
- **clickbait**: Title is sensational but content is minor
- **job_posting**: Hiring announcement
- **sports**: Sports news (unless major event)
- **tool**: Utility tool, calculator, calendar
- **tutorial**: How-to guide, tutorial
- **opinion_only**: Opinion piece without facts

CRITICAL RULES:
- DEFAULT TO LOW SCORES: Most articles should be C or B Tier
- Focus on economics, technology, business, and politics (policy changes, elections, international relations)
- STRICTLY EXCLUDE: Job postings, tools, tutorials, product reviews, academic papers (unless major breakthrough), year titles, celebrity gossip, sports (unless major event)

REASONS: Provide 2-3 brief reasons using this format: "🔹 [Domain]: [Impact]"
{language_examples}
Keep each reason under 25 words. Use relevant emoji (🌍🇺🇸🇨🇳💰📈📉🔬💻⚡🏢🏭📊🎯).

OUTPUT ONLY VALID JSON. No extra text before or after.

ARTICLE DETAILS:
{article_json}

Return JSON:
""".strip()
    
    def __init__(self, language: str = None):
        """
        初始化评分器
        
        Args:
            language: 目标语言 ("zh" 或 "en")，默认使用配置中的语言
        """
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
        self.model = config.OPENAI_MODEL
        self.language = language or config.LANGUAGE
        logger.info(f"AI 评分器初始化，使用模型: {self.model}，语言: {self.language}")
    
    @staticmethod
    def compute_score(
        tier: str,
        impact: int,
        novelty: int,
        credibility: int,
        actionability: int,
        flags: Dict[str, bool]
    ) -> float:
        """
        确定性分数计算函数
        
        Args:
            tier: S/A/B/C 档位
            impact: 影响范围/深度 (0-5)
            novelty: 新颖度 (0-5)
            credibility: 可信度 (0-5)
            actionability: 可操作性 (0-5)
            flags: 标志字典
        
        Returns:
            float: 最终分数 (0-100)
        """
        # Tier 决定基础区间
        tier_ranges = {
            'S': (90, 100),
            'A': (70, 89),
            'B': (40, 69),
            'C': (0, 39)
        }
        
        base_min, base_max = tier_ranges.get(tier.upper(), (0, 39))
        tier_range = base_max - base_min
        
        # 维度分决定区间内位置（加权平均）
        dim_weights = {
            'impact': 0.3,
            'novelty': 0.2,
            'credibility': 0.3,
            'actionability': 0.2
        }
        
        # 归一化维度分到 0-1
        normalized_impact = impact / 5.0
        normalized_novelty = novelty / 5.0
        normalized_credibility = credibility / 5.0
        normalized_actionability = actionability / 5.0
        
        # 加权平均
        dim_score = (
            normalized_impact * dim_weights['impact'] +
            normalized_novelty * dim_weights['novelty'] +
            normalized_credibility * dim_weights['credibility'] +
            normalized_actionability * dim_weights['actionability']
        )
        
        # 在区间内分配分数
        score = base_min + dim_score * tier_range
        
        # Hard rules: caps
        if flags.get('job_posting', False):
            score = min(score, 30.0)
        
        if flags.get('tool', False):
            score = min(score, 20.0)
        
        if flags.get('tutorial', False):
            score = min(score, 25.0)
        
        if flags.get('review_or_list', False):  # 产品评测/列表
            score = min(score, 20.0)
        
        # Clickbait penalty: 降一档或扣 20 分
        if flags.get('clickbait', False):
            if tier.upper() == 'S':
                score = min(score, 89.0)  # 降到 A 档上限
            elif tier.upper() == 'A':
                score = min(score, 69.0)  # 降到 B 档上限
            elif tier.upper() == 'B':
                score = min(score, 39.0)  # 降到 C 档上限
            else:
                score = max(0.0, score - 20.0)
        
        # Sports penalty
        if flags.get('sports', False):
            score = min(score, 30.0)
        
        # Opinion only penalty
        if flags.get('opinion_only', False):
            score = max(0.0, score - 10.0)
        
        # 确保在有效范围内
        return max(0.0, min(100.0, score))
    
    def score_article_structured(self, article: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """
        结构化评分：返回 JSON 解析结果和最终分数
        
        Args:
            article: 新闻数据字典
        
        Returns:
            Tuple[float, Dict]: (最终分数, 结构化数据)
        """
        try:
            # 构建提示词
            article_json = json.dumps({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "source": article.get("source", ""),
                "snippet": article.get("snippet", "")[:500],
                "category": article.get("category", "general"),
            }, indent=2, ensure_ascii=False)
            
            # 根据语言选择示例
            if self.language == "zh":
                language_examples = """Examples (output in Chinese):
- "🌍 地缘政治: 欧美贸易争端可能升级"
- "💰 经济市场: 关税政策可能影响出口企业"
- "🔬 科技创新: AI 技术突破改变行业格局"
Output reasons in Chinese."""
            else:
                language_examples = """Examples (output in English):
- "🌍 Geopolitics: US-EU trade tensions escalating"
- "💰 Economy: Tariff policies may impact exporters"
- "🔬 Tech Innovation: AI breakthrough reshapes industry"
Output reasons in English."""
            
            prompt = self.STRUCTURED_SCORE_PROMPT_TEMPLATE.format(
                article_json=article_json,
                language_examples=language_examples
            )
            
            # 调用 LLM 获取结构化 JSON
            raw_output, parsed_json = self._call_llm_structured(prompt)
            
            # 提取数据
            tier = parsed_json.get("tier", "C").upper()
            impact = int(parsed_json.get("impact", 0))
            novelty = int(parsed_json.get("novelty", 0))
            credibility = int(parsed_json.get("credibility", 0))
            actionability = int(parsed_json.get("actionability", 0))
            flags = parsed_json.get("flags", {})
            reasons = parsed_json.get("reasons", [])
            
            # 确定性计算最终分数
            final_score = self.compute_score(tier, impact, novelty, credibility, actionability, flags)
            
            # 构建结构化结果
            structured_result = {
                "tier": tier,
                "impact": impact,
                "novelty": novelty,
                "credibility": credibility,
                "actionability": actionability,
                "flags": flags,
                "reasons": reasons,
                "final_score": final_score,
                "raw_llm_output": raw_output
            }
            
            logger.debug(f"结构化评分完成: {article.get('title', '')[:50]}... -> {final_score:.2f} (Tier: {tier})")
            
            return final_score, structured_result
            
        except Exception as e:
            logger.error(f"结构化评分失败: {e}，返回默认分数 50.0")
            return 50.0, {
                "tier": "C",
                "impact": 0,
                "novelty": 0,
                "credibility": 0,
                "actionability": 0,
                "flags": {},
                "reasons": ["评分失败，使用默认值"],
                "final_score": 50.0,
                "raw_llm_output": "",
                "error": str(e)
            }
    
    def score_article(self, article: Dict[str, Any]) -> float:
        """
        对单篇新闻评分（兼容接口，内部使用结构化评分）
        
        Args:
            article: 新闻数据字典，包含 title, url, source, snippet 等
        
        Returns:
            float: 评分 (0.0-100.0)
        """
        score, _ = self.score_article_structured(article)
        return score
    
    def score_batch(self, articles: List[Dict[str, Any]], batch_size: int = 5) -> List[Dict[str, Any]]:
        """
        批量评分（含进度显示，使用结构化评分）
        
        Args:
            articles: 新闻列表
            batch_size: 每批次数量（用于日志显示）
        
        Returns:
            List[Dict]: 评分后的新闻列表（添加 score 和 structured_data 字段）
        """
        logger.info(f"开始批量评分 {len(articles)} 条新闻...")
        
        for i, article in enumerate(articles, 1):
            try:
                # 结构化评分
                score, structured_data = self.score_article_structured(article)
                article["score"] = score
                article["structured_data"] = structured_data
                
                # 进度日志
                if i % batch_size == 0 or i == len(articles):
                    logger.info(f"评分进度: {i}/{len(articles)}")
                
            except Exception as e:
                logger.error(f"评分单篇新闻失败 (索引 {i}): {e}")
                article["score"] = 50.0  # 默认中等分数
                article["structured_data"] = {}
        
        logger.info("批量评分完成")
        return articles
    
    def calibrate_batch(self, scored_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批处理校准：强制 S<=3%, A<=10%，防塌缩拉伸
        
        Args:
            scored_items: 已评分的新闻列表（需包含 structured_data）
        
        Returns:
            List[Dict]: 校准后的新闻列表
        """
        if not scored_items:
            return scored_items
        
        # 统计当前分布
        tier_counts = {'S': 0, 'A': 0, 'B': 0, 'C': 0}
        for item in scored_items:
            structured = item.get("structured_data", {})
            tier = structured.get("tier", "C").upper()
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        total = len(scored_items)
        s_ratio = tier_counts.get('S', 0) / total if total > 0 else 0
        a_ratio = tier_counts.get('A', 0) / total if total > 0 else 0
        
        logger.info(f"校准前分布: S={tier_counts.get('S', 0)} ({s_ratio*100:.1f}%), "
                   f"A={tier_counts.get('A', 0)} ({a_ratio*100:.1f}%), "
                   f"B={tier_counts.get('B', 0)}, C={tier_counts.get('C', 0)}")
        
        # 约束 S <= 3%
        max_s = int(total * 0.03)
        if tier_counts.get('S', 0) > max_s:
            # 按分数降序排序，保留前 max_s 个 S，其余降档
            s_items = [item for item in scored_items 
                      if item.get("structured_data", {}).get("tier", "").upper() == "S"]
            s_items.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            for item in s_items[max_s:]:
                structured = item.get("structured_data", {})
                # 降档到 A
                structured["tier"] = "A"
                # 重新计算分数（在 A 档范围内）
                old_score = item.get("score", 0)
                if old_score > 89:
                    # 调整到 A 档上限附近
                    item["score"] = 89.0
                    structured["final_score"] = 89.0
                tier_counts['S'] -= 1
                tier_counts['A'] = tier_counts.get('A', 0) + 1
                logger.debug(f"降档 S->A: {item.get('title', '')[:50]}...")
        
        # 约束 A <= 10%（包括原来的 A 和降档来的 S）
        max_a = int(total * 0.10)
        if tier_counts.get('A', 0) > max_a:
            a_items = [item for item in scored_items 
                      if item.get("structured_data", {}).get("tier", "").upper() == "A"]
            a_items.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            for item in a_items[max_a:]:
                structured = item.get("structured_data", {})
                # 降档到 B
                structured["tier"] = "B"
                # 调整分数到 B 档上限
                old_score = item.get("score", 0)
                if old_score > 69:
                    item["score"] = 69.0
                    structured["final_score"] = 69.0
                tier_counts['A'] -= 1
                tier_counts['B'] = tier_counts.get('B', 0) + 1
                logger.debug(f"降档 A->B: {item.get('title', '')[:50]}...")
        
        # 防塌缩：如果分布太集中，做小幅拉伸
        scores = [item.get("score", 0) for item in scored_items]
        if len(scores) > 1:
            import statistics
            score_std = statistics.stdev(scores) if len(scores) > 1 else 0
            score_sorted = sorted(scores)
            p90 = score_sorted[int(len(score_sorted) * 0.9)] if len(score_sorted) > 0 else 0
            p10 = score_sorted[int(len(score_sorted) * 0.1)] if len(score_sorted) > 0 else 0
            score_range = p90 - p10
            
            # 如果标准差 < 15 或范围 < 30，做拉伸
            if score_std < 15 or score_range < 30:
                logger.info(f"检测到分数塌缩 (std={score_std:.2f}, range={score_range:.2f})，进行拉伸...")
                
                # 按分数排序
                sorted_items = sorted(scored_items, key=lambda x: x.get("score", 0))
                quartile_size = len(sorted_items) // 4
                
                # Top quartile +3
                for item in sorted_items[-quartile_size:]:
                    old_score = item.get("score", 0)
                    new_score = min(100.0, old_score + 3.0)
                    item["score"] = new_score
                    structured = item.get("structured_data", {})
                    if structured:
                        structured["final_score"] = new_score
                
                # Bottom quartile -3
                for item in sorted_items[:quartile_size]:
                    old_score = item.get("score", 0)
                    new_score = max(0.0, old_score - 3.0)
                    item["score"] = new_score
                    structured = item.get("structured_data", {})
                    if structured:
                        structured["final_score"] = new_score
                
                logger.info("拉伸完成")
        
        # 重新统计
        tier_counts_after = {'S': 0, 'A': 0, 'B': 0, 'C': 0}
        for item in scored_items:
            structured = item.get("structured_data", {})
            tier = structured.get("tier", "C").upper()
            tier_counts_after[tier] = tier_counts_after.get(tier, 0) + 1
        
        logger.info(f"校准后分布: S={tier_counts_after.get('S', 0)}, "
                   f"A={tier_counts_after.get('A', 0)}, "
                   f"B={tier_counts_after.get('B', 0)}, "
                   f"C={tier_counts_after.get('C', 0)}")
        
        return scored_items
    
    def _call_llm_structured(self, prompt: str, max_retries: int = 3) -> Tuple[str, Dict[str, Any]]:
        """
        调用 LLM 获取结构化 JSON 输出（含重试和严格校验）
        
        Args:
            prompt: 提示词
            max_retries: 最大重试次数
        
        Returns:
            Tuple[str, Dict]: (原始输出, 解析后的 JSON)
        """
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a news analysis assistant. You MUST return ONLY valid JSON, no extra text before or after. Your response must be parseable by json.loads()."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=300,  # JSON 输出需要更多 tokens
                    timeout=config.MODEL_TIMEOUT
                )
                
                raw_output = response.choices[0].message.content.strip()
                
                # 尝试提取 JSON（去除可能的 markdown 代码块）
                json_text = raw_output
                if "```json" in json_text:
                    json_text = json_text.split("```json")[1].split("```")[0].strip()
                elif "```" in json_text:
                    json_text = json_text.split("```")[1].split("```")[0].strip()
                
                # 严格解析 JSON
                try:
                    parsed_json = json.loads(json_text)
                    
                    # 验证必需字段
                    required_fields = ["tier", "impact", "novelty", "credibility", "actionability", "flags", "reasons"]
                    for field in required_fields:
                        if field not in parsed_json:
                            raise ValueError(f"缺少必需字段: {field}")
                    
                    # 验证 tier
                    if parsed_json["tier"].upper() not in ["S", "A", "B", "C"]:
                        raise ValueError(f"无效的 tier: {parsed_json['tier']}")
                    
                    # 验证维度分范围
                    for dim in ["impact", "novelty", "credibility", "actionability"]:
                        val = int(parsed_json[dim])
                        if val < 0 or val > 5:
                            raise ValueError(f"{dim} 超出范围 [0, 5]: {val}")
                    
                    logger.debug(f"✅ JSON 解析成功 (尝试 {attempt + 1})")
                    return raw_output, parsed_json
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON 解析失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    logger.debug(f"原始输出: {raw_output[:200]}...")
                    if attempt < max_retries:
                        continue
                    else:
                        raise
                except ValueError as e:
                    logger.warning(f"JSON 验证失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    if attempt < max_retries:
                        continue
                    else:
                        raise
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                else:
                    logger.error(f"LLM 调用失败，已达最大重试次数: {e}")
                    raise
        
        # 兜底：返回默认值
        default_json = {
            "tier": "C",
            "impact": 0,
            "novelty": 0,
            "credibility": 0,
            "actionability": 0,
            "flags": {},
            "reasons": ["解析失败，使用默认值"]
        }
        return "", default_json
    
    def _call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> float:
        """
        调用 LLM 并解析评分（含重试）
        
        Args:
            prompt: 提示词
            max_retries: 最大重试次数
        
        Returns:
            float: 评分 (0.0-100.0)
        """
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a cynical, hard-to-impress tech investor. You evaluate news with extreme skepticism. Return your classification in the format: 'TIER: [S/A/B/C], SCORE: [number]'."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=50,  # 需要返回 Tier 和 Score
                    timeout=config.MODEL_TIMEOUT
                )
                
                raw_score = response.choices[0].message.content.strip()
                
                # 🔍 调试：记录原始返回值
                logger.debug(f"LLM 原始返回: '{raw_score}'")
                
                # 解析评分
                score = self._parse_score(raw_score)
                logger.debug(f"解析后分数: {score:.2f} (0-100分制)")
                
                # 验证范围
                if 0.0 <= score <= 100.0:
                    return score
                else:
                    logger.warning(f"评分超出范围: {score}，尝试修正")
                    return max(0.0, min(100.0, score))
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                else:
                    logger.error(f"LLM 调用失败，已达最大重试次数: {e}")
                    raise
        
        return 50.0  # 兜底分数
    
    def _parse_score(self, raw_text: str) -> float:
        """
        解析 LLM 返回的评分（支持 Tier 格式和纯数字格式）
        
        Args:
            raw_text: LLM 返回的原始文本（可能是 "TIER: S, SCORE: 95" 或纯数字）
        
        Returns:
            float: 评分 (0.0-100.0)
        
        Raises:
            ValueError: 无法解析评分
        """
        try:
            raw_text = raw_text.strip()
            
            # 方法 1: 解析 Tier 格式 "TIER: S, SCORE: 95" 或 "TIER: A, SCORE: 75"
            tier_pattern = r'TIER:\s*([SABC]),\s*SCORE:\s*(\d+\.?\d*)'
            tier_match = re.search(tier_pattern, raw_text, re.IGNORECASE)
            if tier_match:
                tier = tier_match.group(1).upper()
                score = float(tier_match.group(2))
                
                # 验证分数是否在对应 Tier 范围内
                tier_ranges = {
                    'S': (90, 100),
                    'A': (70, 89),
                    'B': (40, 69),
                    'C': (0, 39)
                }
                min_score, max_score = tier_ranges.get(tier, (0, 100))
                
                # 如果分数不在范围内，调整到范围内
                if score < min_score:
                    score = min_score
                elif score > max_score:
                    score = max_score
                
                logger.debug(f"解析到 Tier: {tier}, Score: {score}")
                return score
            
            # 方法 2: 直接解析数字（向后兼容）
            numbers = re.findall(r'\d+\.?\d*', raw_text)
            if numbers:
                score = float(numbers[0])
                
                # 如果 LLM 返回了 0-10 分制的分数，自动转换为 0-100
                if score <= 10.0:
                    score = score * 10
                
                return score
            
            # 方法 3: 尝试解析 JSON
            try:
                data = json.loads(raw_text)
                if isinstance(data, dict) and "score" in data:
                    score = float(data["score"])
                    if score <= 10.0:
                        score = score * 10
                    return score
            except:
                pass
            
            # 无法解析
            raise ValueError(f"无法从文本中解析评分: {raw_text}")
            
        except Exception as e:
            logger.warning(f"评分解析失败: {e}，原文: {raw_text}")
            raise
    
    def _is_job_posting(self, article: Dict[str, Any]) -> bool:
        """
        检测文章是否为招聘信息
        
        Args:
            article: 新闻数据字典
        
        Returns:
            bool: 如果是招聘信息返回 True
        """
        # 招聘相关的关键词（中英文）
        job_keywords = [
            "hiring", "we're hiring", "we are hiring", "job opening", "job posting",
            "recruiting", "recruitment", "career", "apply to role", "join our team",
            "招聘", "诚聘", "招人", "职位", "岗位", "应聘", "求职", "加入我们"
        ]
        
        # 检查标题和摘要
        title = article.get("title", "").lower()
        snippet = article.get("snippet", "").lower()
        combined_text = f"{title} {snippet}"
        
        # 如果包含招聘关键词，很可能是招聘信息
        for keyword in job_keywords:
            if keyword.lower() in combined_text:
                return True
        
        return False
    
    def _detect_clickbait(self, article: Dict[str, Any]) -> float:
        """
        检测点击诱饵：标题夸张但内容空洞
        
        Args:
            article: 新闻数据字典
        
        Returns:
            float: 惩罚分数（0-20），如果是点击诱饵返回 20，否则返回 0
        """
        title = article.get("title", "").lower()
        snippet = article.get("snippet", "").lower()
        
        # 夸张的标题关键词
        sensational_keywords = [
            "revolutionary", "shocking", "game-changing", "this changes everything",
            "you won't believe", "amazing", "incredible", "unbelievable",
            "震惊", "颠覆", "革命性", "改变一切", "不敢相信", "惊人"
        ]
        
        # 检查标题是否包含夸张词汇
        has_sensational_title = any(keyword in title for keyword in sensational_keywords)
        
        if not has_sensational_title:
            return 0.0
        
        # 如果标题夸张，检查内容是否匹配
        # 如果摘要很短（<50字符）或包含"minor", "update", "announcement"等词，可能是点击诱饵
        minor_update_keywords = [
            "minor", "update", "announcement", "release", "version",
            "小幅", "更新", "发布", "版本", "升级"
        ]
        
        snippet_is_minor = len(snippet) < 50 or any(keyword in snippet for keyword in minor_update_keywords)
        
        # 如果标题夸张但内容很普通，判定为点击诱饵
        if snippet_is_minor:
            logger.debug(f"检测到点击诱饵: 标题夸张但内容空洞 | {title[:50]}...")
            return 20.0
        
        return 0.0


