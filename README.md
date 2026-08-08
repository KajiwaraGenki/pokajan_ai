# ポカジャン 打牌解析 Web

## 必要ファイル

- `streamlit_app.py`
- `pokajan_simulator_v24.py`
- `pokajan_tuned_config.json`
- `requirements.txt`

## ローカル起動

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Community Cloud で公開

1. この4ファイルをGitHubリポジトリへアップロード
2. Streamlit Community Cloudで「Create app」
3. GitHubリポジトリを選択
4. Entrypointに `streamlit_app.py` を指定
5. Deploy

学習済みJSONは、正式ルール対応の `pokajan_simulator_v23_training.py` で生成したものを
`pokajan_tuned_config.json` という名前で置いてください。
