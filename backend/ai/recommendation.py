import numpy as np
import pandas as pd
from typing import List, Dict, Any

class TourismRecommender:
    def __init__(self):
        # Trọng số thuật toán (Configurable Weights)
        self.W_CATEGORY = 0.35
        self.W_WEATHER = 0.20
        self.W_BUDGET = 0.20
        self.W_RATING = 0.15
        self.W_POPULARITY = 0.10

    def compute_category_score(self, dest_category: str, user_interests: List[str]) -> float:
        """Tính độ tương đồng về danh mục / sở thích"""
        if not user_interests or not dest_category:
            return 0.5
        
        dest_cat_lower = str(dest_category).lower()
        for interest in user_interests:
            if interest.lower() in dest_cat_lower or dest_cat_lower in interest.lower():
                return 1.0
        return 0.2

    def compute_budget_score(self, estimated_cost: float, user_budget: str) -> float:
        """Tính độ phù hợp ngân sách (Low, Medium, High)"""
        user_budget = (user_budget or "Medium").lower()
        if user_budget == "low":
            if estimated_cost == 0:
                return 1.0
            elif estimated_cost <= 100000:
                return 0.85
            elif estimated_cost <= 300000:
                return 0.5
            return 0.1
        elif user_budget == "medium":
            if 50000 <= estimated_cost <= 600000:
                return 1.0
            return 0.7
        else: # High
            if estimated_cost >= 300000:
                return 1.0
            return 0.8

    def compute_weather_score(self, is_indoor: bool, is_outdoor: bool, current_weather: str) -> float:
        """Tính độ thích ứng thời tiết thời gian thực"""
        current_weather = (current_weather or "sunny").lower()
        if "rain" in current_weather or "mưa" in current_weather:
            if is_indoor:
                return 1.0
            elif is_outdoor:
                return 0.2
            return 0.6
        else: # Trời nắng / râm mát
            if is_outdoor:
                return 1.0
            return 0.8

    def rank_destinations(
        self, 
        destinations: List[Dict[str, Any]], 
        user_interests: List[str], 
        user_budget: str = "Medium", 
        current_weather: str = "sunny",
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Thuật toán xếp hạng toàn bộ điểm đến trong dataset"""
        if not destinations:
            return []

        df = pd.DataFrame(destinations)

        # 1. Chuẩn hóa Rating (0 -> 1)
        max_rating = 5.0
        df['norm_rating'] = df['rating'].fillna(0.0) / max_rating

        # 2. Chuẩn hóa Popularity (dựa trên review_count)
        max_reviews = df['review_count'].max() if df['review_count'].max() > 0 else 1
        df['norm_popularity'] = df['review_count'].fillna(0) / max_reviews

        # 3. Tính toán các điểm thành phần
        ranked_results = []
        for idx, row in df.iterrows():
            s_cat = self.compute_category_score(row.get('category_name', ''), user_interests)
            s_budget = self.compute_budget_score(row.get('estimated_cost', 0.0), user_budget)
            s_weather = self.compute_weather_score(
                bool(row.get('is_indoor', False)), 
                bool(row.get('is_outdoor', True)), 
                current_weather
            )
            s_rating = float(row['norm_rating'])
            s_pop = float(row['norm_popularity'])

            # Công thức Hybrid Score (thang điểm 100%)
            final_score = (
                self.W_CATEGORY * s_cat +
                self.W_WEATHER * s_weather +
                self.W_BUDGET * s_budget +
                self.W_RATING * s_rating +
                self.W_POPULARITY * s_pop
            ) * 100.0

            # Tạo lý do gợi ý tự động (Explainable AI - XAI)
            reasons = []
            if s_cat >= 0.8:
                reasons.append("Phù hợp sở thích cá nhân")
            if s_budget >= 0.8:
                reasons.append("Tối ưu theo ngân sách")
            if s_weather >= 0.9:
                reasons.append("Lý tưởng với thời tiết hiện tại")
            if not reasons:
                reasons.append("Điểm đến được cộng đồng đánh giá cao")

            dest_dict = row.to_dict()
            dest_dict['match_score'] = round(final_score, 1)
            dest_dict['recommend_reasons'] = reasons
            ranked_results.append(dest_dict)

        # Sắp xếp giảm dần theo Match Score
        ranked_results.sort(key=lambda x: x['match_score'], reverse=True)
        return ranked_results[:top_k]

# Khởi tạo singleton recommender instance
recommender = TourismRecommender()