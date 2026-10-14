import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session
from backend import models

# Trọng số hành vi thực tế
ACTION_WEIGHTS = {
    "VIEW": 1.0,
    "CLICK_RECOMMENDATION": 1.5,
    "SEARCH": 2.0,
    "FAVORITE": 3.5,
    "REVIEW": 5.0
}

class BehaviorMatrixRecommender:
    def __init__(self, n_components: int = 5):
        self.n_components = n_components
        self.user_item_matrix = None
        self.predicted_matrix = None
        self.dest_similarity_matrix = None
        self.user_ids = []
        self.destination_ids = []

    def fit_from_db(self, db: Session):
        """1. Đọc toàn bộ bảng user_behaviors và destinations để huấn luyện ma trận"""
        behaviors = db.query(
            models.UserBehavior.user_id,
            models.UserBehavior.destination_id,
            models.UserBehavior.action,
            models.UserBehavior.weight
        ).all()

        if not behaviors or len(behaviors) < 3:
            return False

        df = pd.DataFrame([
            {
                "user_id": b.user_id,
                "destination_id": b.destination_id,
                "weight": ACTION_WEIGHTS.get(b.action, b.weight or 1.0)
            }
            for b in behaviors
        ])

        # Tổng hợp trọng số nếu user có nhiều hành vi trên cùng 1 destination
        grouped_df = df.groupby(["user_id", "destination_id"])["weight"].sum().reset_index()

        # Tạo Pivot Table (Ma trận User - Item)
        pivot = grouped_df.pivot(index="user_id", columns="destination_id", values="weight").fillna(0.0)
        self.user_item_matrix = pivot
        self.user_ids = list(pivot.index)
        self.destination_ids = list(pivot.columns)

        # 2. Phân rã Ma trận bằng TruncatedSVD (Matrix Factorization)
        n_features = min(self.n_components, pivot.shape[1] - 1, pivot.shape[0] - 1)
        if n_features >= 1:
            svd = TruncatedSVD(n_components=n_features, random_state=42)
            user_features = svd.fit_transform(pivot.values)
            # Tái tạo ma trận điểm dự đoán hoàn chỉnh
            self.predicted_matrix = pd.DataFrame(
                np.dot(user_features, svd.components_),
                index=self.user_ids,
                columns=self.destination_ids
            )

        # 3. Tính ma trận Cosine Similarity giữa các Items dựa trên hành vi cộng đồng
        item_user_matrix = pivot.T.values
        self.dest_similarity_matrix = pd.DataFrame(
            cosine_similarity(item_user_matrix),
            index=self.destination_ids,
            columns=self.destination_ids
        )
        return True

    def recommend_for_user(self, user_id: int, top_k: int = 8) -> list:
        """Gợi ý điểm đến cá nhân hóa cho User dựa trên Ma trận SVD đã học"""
        if self.predicted_matrix is None or user_id not in self.user_ids:
            return []

        # Lấy điểm số dự đoán của user này đối với tất cả địa điểm
        user_predictions = self.predicted_matrix.loc[user_id].copy()

        # Loại bỏ các địa điểm mà user đã xem/thích nhiều lần để ưu tiên khám phá mới
        interacted_items = self.user_item_matrix.loc[user_id]
        already_seen = interacted_items[interacted_items > 0].index

        # Giảm trọng số của các điểm đã tương tác quá sâu
        user_predictions[already_seen] *= 0.2

        top_dest_ids = user_predictions.sort_values(ascending=False).head(top_k).index.tolist()
        return [int(d_id) for d_id in top_dest_ids]

    def recommend_by_recent_behavior(self, recent_dest_id: int, top_k: int = 6) -> list:
        """Nếu user vừa click vào 1 địa điểm, dùng Item-Item Matrix tìm các địa điểm tương đồng nhất"""
        if self.dest_similarity_matrix is None or recent_dest_id not in self.dest_similarity_matrix.index:
            return []

        similar_scores = self.dest_similarity_matrix.loc[recent_dest_id].sort_values(ascending=False)
        # Bỏ qua chính địa điểm hiện tại
        similar_dest_ids = similar_scores.iloc[1:top_k + 1].index.tolist()
        return [int(d_id) for d_id in similar_dest_ids]

matrix_engine = BehaviorMatrixRecommender()