"""多 API 配置解析模組。

從 .env 讀取多個 API 設定，支援主/副 API 分類，
以及類別級預設並發與個別覆蓋。
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# 類別級預設並發（硬編碼）
MAIN_DEFAULT_LIMIT = 10
FALLBACK_DEFAULT_LIMIT = 1

# 每個 API 獨立的最小請求間隔（秒）
REQUEST_INTERVAL = 1


@dataclass
class ApiConfig:
    """單個 API Key 的完整配置"""

    api_id: str         # "API1", "API2" ...
    key: str            # API_KEY
    model_provider: str # 供應商名稱
    model: str          # 模型名稱
    base_url: str       # API 端點
    api_type: str       # "main" | "fallback"
    parallel_limit: int # 最終解析後的並發上限

    # 運行時狀態（不從 .env 讀取）
    strike: int = 0
    cooldown_until: float = 0.0

    @property
    def is_cooling_down(self) -> bool:
        """是否正在冷卻中"""
        import time
        return time.monotonic() < self.cooldown_until

    def mark_429(self) -> None:
        """記錄一次 429 錯誤，返回該 API 是否應永久停用"""
        import time
        self.strike += 1
        if self.strike == 1:
            self.cooldown_until = time.monotonic() + 60

    @property
    def is_permanently_disabled(self) -> bool:
        """第二次 429 後永久停用"""
        return self.strike >= 2

    @property
    def is_available(self) -> bool:
        """該 API 當前是否可用（未冷卻且未永久停用）"""
        return not self.is_cooling_down and not self.is_permanently_disabled


def load_api_configs() -> list[ApiConfig]:
    """從 .env 載入所有 API 配置，返回已解析的 ApiConfig 列表。

    掃描 API1_, API2_, API3_... 直到找不到下一個編號。
    每個 API 必填：_TYPE, _MODEL_PROVIDER, _MODEL, _API_KEY, _BASE_URL
    可選：_PARALLEL_LIMIT（覆蓋類別預設）
    """
    configs: list[ApiConfig] = []
    idx = 1

    while True:
        prefix = f"API{idx}_"
        api_type = os.getenv(f"{prefix}TYPE", "").strip().lower()

        if not api_type:
            break  # 沒有更多 API 了

        if api_type not in ("main", "fallback"):
            print(f"  警告：API{idx} 的 TYPE '{api_type}' 無效，跳過（應為 main 或 fallback）")
            idx += 1
            continue

        api_key = os.getenv(f"{prefix}API_KEY", "").strip()
        if not api_key:
            print(f"  警告：API{idx} 缺少 API_KEY，跳過")
            idx += 1
            continue

        model = os.getenv(f"{prefix}MODEL", "").strip()
        if not model:
            print(f"  警告：API{idx} 缺少 MODEL，跳過")
            idx += 1
            continue

        base_url = os.getenv(f"{prefix}BASE_URL", "").strip()
        if not base_url:
            print(f"  警告：API{idx} 缺少 BASE_URL，跳過")
            idx += 1
            continue
        model_provider = os.getenv(f"{prefix}MODEL_PROVIDER", "").strip()

        # 解析並發上限：獨立值 > 類別預設
        limit_str = os.getenv(f"{prefix}PARALLEL_LIMIT", "").strip()
        if limit_str:
            try:
                parallel_limit = int(limit_str)
            except ValueError:
                print(f"  警告：API{idx} 的 PARALLEL_LIMIT '{limit_str}' 無效，使用類別預設")
                parallel_limit = MAIN_DEFAULT_LIMIT if api_type == "main" else FALLBACK_DEFAULT_LIMIT
        else:
            parallel_limit = MAIN_DEFAULT_LIMIT if api_type == "main" else FALLBACK_DEFAULT_LIMIT

        configs.append(ApiConfig(
            api_id=f"API{idx}",
            key=api_key,
            model_provider=model_provider,
            model=model,
            base_url=base_url,
            api_type=api_type,
            parallel_limit=parallel_limit,
        ))

        idx += 1

    if not configs:
        # 向後相容：如果沒有 API1_ 系列設定，回退到舊的單一 API 格式
        legacy_key = os.getenv("API_KEY", "").strip()
        if legacy_key:
            print("  使用舊版單一 API 配置（向後相容）")
            configs.append(ApiConfig(
                api_id="API1",
                key=legacy_key,
                model_provider=os.getenv("MODEL_PROVIDER", "").strip(),
                model=os.getenv("MODEL", "").strip(),
                base_url=os.getenv("BASE_URL", "").strip(),
                api_type="main",
                parallel_limit=MAIN_DEFAULT_LIMIT,
            ))

    return configs