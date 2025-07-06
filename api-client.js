/**
 * FX Forecast API Client
 * API連携用のJavaScriptクライアント
 */

class FXForecastAPIClient {
    constructor(baseURL = 'http://localhost:8767/api/v1') {
        this.baseURL = baseURL;
        this.headers = {
            'Content-Type': 'application/json',
        };
    }

    /**
     * APIエラーハンドリング
     */
    async handleResponse(response) {
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new APIError(
                response.status,
                errorData.detail || response.statusText,
                errorData
            );
        }
        return response.json();
    }

    /**
     * 分析履歴を取得
     */
    async getHistory(params = {}) {
        const queryParams = new URLSearchParams();
        if (params.skip) queryParams.append('skip', params.skip);
        if (params.limit) queryParams.append('limit', params.limit);
        if (params.currency_pair) queryParams.append('currency_pair', params.currency_pair);
        if (params.start_date) queryParams.append('start_date', params.start_date);
        if (params.end_date) queryParams.append('end_date', params.end_date);

        const response = await fetch(
            `${this.baseURL}/history/?${queryParams}`,
            { headers: this.headers }
        );
        return this.handleResponse(response);
    }

    /**
     * 特定の分析を取得
     */
    async getForecast(forecastId) {
        const response = await fetch(
            `${this.baseURL}/history/${forecastId}`,
            { headers: this.headers }
        );
        return this.handleResponse(response);
    }

    /**
     * コメント関連API
     */
    comments = {
        /**
         * 分析に対するコメント一覧を取得
         */
        getByForecast: async (forecastId) => {
            const response = await fetch(
                `${this.baseURL}/comments/forecasts/${forecastId}/comments`,
                { headers: this.headers }
            );
            return this.handleResponse(response);
        },

        /**
         * 新規コメントを作成
         */
        create: async (data) => {
            const response = await fetch(
                `${this.baseURL}/comments/comments`,
                {
                    method: 'POST',
                    headers: this.headers,
                    body: JSON.stringify(data)
                }
            );
            return this.handleResponse(response);
        },

        /**
         * コメントを更新
         */
        update: async (commentId, data) => {
            const response = await fetch(
                `${this.baseURL}/comments/comments/${commentId}`,
                {
                    method: 'PUT',
                    headers: this.headers,
                    body: JSON.stringify(data)
                }
            );
            return this.handleResponse(response);
        },

        /**
         * コメントを削除
         */
        delete: async (commentId) => {
            const response = await fetch(
                `${this.baseURL}/comments/comments/${commentId}`,
                {
                    method: 'DELETE',
                    headers: this.headers
                }
            );
            return this.handleResponse(response);
        },

        /**
         * AIに質問
         */
        askAI: async (data) => {
            const response = await fetch(
                `${this.baseURL}/comments/comments/ask-ai`,
                {
                    method: 'POST',
                    headers: this.headers,
                    body: JSON.stringify(data)
                }
            );
            return this.handleResponse(response);
        }
    };

    /**
     * 分析関連API
     */
    analysis = {
        /**
         * チャート分析を実行 (V2)
         */
        analyzeV2: async (formData) => {
            const response = await fetch(
                `${this.baseURL}/analysis/analyze/v2`,
                {
                    method: 'POST',
                    body: formData
                }
            );
            return this.handleResponse(response);
        },

        /**
         * チャート分析を実行 (レガシー)
         */
        analyze: async (formData) => {
            const response = await fetch(
                `${this.baseURL}/analysis/analyze`,
                {
                    method: 'POST',
                    body: formData
                }
            );
            return this.handleResponse(response);
        }
    };

    /**
     * レビュー関連API
     */
    review = {
        /**
         * 予測レビューを作成
         */
        create: async (formData) => {
            const response = await fetch(
                `${this.baseURL}/review/create`,
                {
                    method: 'POST',
                    body: formData
                }
            );
            return this.handleResponse(response);
        },

        /**
         * レビュー履歴を取得
         */
        getHistory: async (params = {}) => {
            const queryParams = new URLSearchParams();
            if (params.skip) queryParams.append('skip', params.skip);
            if (params.limit) queryParams.append('limit', params.limit);
            if (params.forecast_id) queryParams.append('forecast_id', params.forecast_id);
            if (params.start_date) queryParams.append('start_date', params.start_date);
            if (params.end_date) queryParams.append('end_date', params.end_date);

            const response = await fetch(
                `${this.baseURL}/review/history?${queryParams}`,
                { headers: this.headers }
            );
            return this.handleResponse(response);
        },

        /**
         * 特定のレビューを取得
         */
        get: async (reviewId) => {
            const response = await fetch(
                `${this.baseURL}/review/${reviewId}`,
                { headers: this.headers }
            );
            return this.handleResponse(response);
        }
    };

    /**
     * トレードレビュー関連API
     */
    tradeReview = {
        /**
         * トレードを分析
         */
        analyze: async (formData) => {
            const response = await fetch(
                `${this.baseURL}/trade-review/analyze`,
                {
                    method: 'POST',
                    body: formData
                }
            );
            return this.handleResponse(response);
        },

        /**
         * トレードレビュー一覧を取得
         */
        getList: async (params = {}) => {
            const queryParams = new URLSearchParams();
            if (params.skip) queryParams.append('skip', params.skip);
            if (params.limit) queryParams.append('limit', params.limit);
            if (params.currency_pair) queryParams.append('currency_pair', params.currency_pair);

            const response = await fetch(
                `${this.baseURL}/trade-review/?${queryParams}`,
                { headers: this.headers }
            );
            return this.handleResponse(response);
        },

        /**
         * 特定のトレードレビューを取得
         */
        get: async (reviewId) => {
            const response = await fetch(
                `${this.baseURL}/trade-review/${reviewId}`,
                { headers: this.headers }
            );
            return this.handleResponse(response);
        },

        /**
         * トレードレビューのコメントを取得
         */
        getComments: async (reviewId) => {
            const response = await fetch(
                `${this.baseURL}/trade-review/${reviewId}/comments`,
                { headers: this.headers }
            );
            return this.handleResponse(response);
        },

        /**
         * トレードレビューにコメントを追加
         */
        addComment: async (data) => {
            const response = await fetch(
                `${this.baseURL}/trade-review/comments`,
                {
                    method: 'POST',
                    headers: this.headers,
                    body: JSON.stringify(data)
                }
            );
            return this.handleResponse(response);
        },

        /**
         * トレードレビューについてAIに質問
         */
        askAI: async (data) => {
            const response = await fetch(
                `${this.baseURL}/trade-review/comments/ask-ai`,
                {
                    method: 'POST',
                    headers: this.headers,
                    body: JSON.stringify(data)
                }
            );
            return this.handleResponse(response);
        },

        /**
         * トレードレビューを削除
         */
        delete: async (reviewId) => {
            const response = await fetch(
                `${this.baseURL}/trade-review/${reviewId}`,
                {
                    method: 'DELETE',
                    headers: this.headers
                }
            );
            return this.handleResponse(response);
        }
    };
}

/**
 * カスタムAPIエラークラス
 */
class APIError extends Error {
    constructor(status, message, data = {}) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}

/**
 * ユーティリティ関数
 */
const FXForecastUtils = {
    /**
     * コメントタイプのラベルを取得
     */
    getCommentTypeLabel(type) {
        const labels = {
            'question': '質問',
            'answer': '回答',
            'note': 'メモ'
        };
        return labels[type] || type;
    },

    /**
     * 日時をフォーマット
     */
    formatDateTime(dateString) {
        return new Date(dateString).toLocaleString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    /**
     * FormDataにファイルを追加（nullチェック付き）
     */
    appendFileToFormData(formData, fieldName, file) {
        if (file && file instanceof File) {
            formData.append(fieldName, file);
        }
    },

    /**
     * エラーメッセージを取得
     */
    getErrorMessage(error) {
        if (error instanceof APIError) {
            return error.message;
        }
        return error.message || 'エラーが発生しました';
    }
};

// グローバルに公開
window.FXForecastAPIClient = FXForecastAPIClient;
window.FXForecastUtils = FXForecastUtils;