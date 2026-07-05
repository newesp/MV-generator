# MV Generator — 完整規劃文件
> 最後更新：2026-07-03 13:22

本文件彙整了從專案啟動討論至今的所有關鍵決策、需求演進、程式碼現況、以及最終的全面檢視結論。作為後續開發的唯一真實來源 (Single Source of Truth)。

---

## 2026-07-03 重新評估與執行更新

### 產品定位修正
目前專案應先定位為 **本機 MVP：音樂卡點/段落分析 + 圖像素材 + 自動剪輯合成器**。AI 生影片與對嘴功能先作為可插拔外掛，不應在 MVP 階段把每個 beat 都綁定外部 API 呼叫。

### 對嘴方向修正
使用者確認目標是 **人物照 + 歌曲 MP3 → 生成會對嘴/唱歌的人物 MP4**。官方 LivePortrait 已透過 `client.view_api()` 驗證為 `source image + driving video → video` 的 video-driven 模式，並非 audio-driven 對嘴模型。

因此 MVP 第一個 open-source provider 改選 **SadTalker**：
- 候選 `vinthony/SadTalker` 目前為 `BUILD_ERROR`，不可用。
- 已驗證 `kevinwang676/SadTalker` 可讀取 Gradio API，輸入為 `source_image + input_audio`，輸出為 `generated_video`。
- 後端預設 `lipsync.provider = sadtalker_hf`，`space_id = kevinwang676/SadTalker`。
- 使用者已同意以 `inputs/Gina (1).png` + `outputs/segment_000.m4a` 上傳到 HF 做單段測試。實測發現：
  - `gradio_client==2.5.0` 對該舊版 Space 回報 `Unknown protocol: ws`。
  - 降版至 `gradio_client==0.8.1` 後可進入 prediction，但免費 Space 在 10 分鐘內未返回結果。
  - `segment_000.m4a` 長度約 0.75 秒，因此 timeout 較可能是 HF 免費 Space 冷啟動/排隊/資源不足，而非音訊太長。
  - 其他 SadTalker forks 如 `vinthony/SadTalker`、`lithiumice/SadTalker`、`4Taps/SadTalker`、`Datasculptor/SadTalker` 目前皆為 `BUILD_ERROR`。

### 30 秒 MVP provider 修正
為了先產出約 30 秒 MVP MV，新增並改採 **Wav2Lip ZeroGPU** 作為預設 provider：
- 已檢查 `fatma812/Wav2lip-ZeroGPU2`：Gradio API 可讀，`input_image + input_audio -> output_video`，endpoint 為 `/run_inference`。
- 已檢查 `pragnakalp/Wav2lip-ZeroGPU`：Gradio API 可讀，`input_image + input_audio -> output`，endpoint 為 `/run_infrence`（Space 內拼字如此）。
- 已檢查 `manavisrani07/gradio-lipsync-wav2lip`：API 可讀，但需要更多參數（checkpoint/padding/resize）。
- 已檢查 `fffiloni/EchoMimic`、`fffiloni/echomimic-v2`：Space 可載入，但目前無法透過 `gradio_client` 取得 API info。
- MuseTalk 搜尋結果多數為 Docker Space 或 API 形狀不穩定，暫不作為第一個 MVP endpoint。

目前預設：
- `lipsync.provider = wav2lip_zerogpu_hf`
- `lipsync.space_id = fatma812/Wav2lip-ZeroGPU2`
- `lipsync.api_name = /run_inference`
- `audio.max_duration_seconds = 30`
- `audio.segment_mode = sections`
- `audio.section_count = 1`

實測結果：
- 使用者明確同意上傳 `inputs/Gina (1).png` 與 `inputs/Café_no_Mar.mp3` 的前 30 秒音訊到 `fatma812/Wav2lip-ZeroGPU2`。
- 第一次測試因 `gradio_client==0.8.1` 不支援 `sse_v3`，Wav2Lip 失敗並 fallback 成靜態影片。
- 將 `gradio_client` 升回 `2.5.0` 後，Wav2Lip prediction 成功，pipeline 產出 `outputs/final_mv.mp4`。
- 初次 Wav2Lip 回傳影片比音訊長約 2 秒，因此 `merger.py` 已改為以原始音訊長度 `-t` 裁切合併輸出。
- 最終 `ffprobe` 驗證輸出為 H.264/AAC MP4，video 約 28.73 秒、audio 約 28.66 秒。

### 本次已完成修正
- 新增根目錄 `.gitignore`，排除 `backend/venv`、`frontend/node_modules`、`inputs/*`、`outputs/*`、build 產物與 `.env`。
- 新增 `inputs/.gitkeep`、`outputs/.gitkeep`，保留資料夾結構但不追蹤實際素材/輸出。
- 新增根目錄 `README.md`，說明專案定位、啟動方式與目前限制。
- `backend/main.py` 改為以 `backend` 目錄解析 config 內的相對路徑，避免啟動位置不同造成 inputs/outputs 寫錯。
- `backend/main.py` 上傳檔名改用 `os.path.basename()`，降低路徑穿越風險。
- `backend/src/merger.py` 新增 FFmpeg 錯誤檢查，失敗時回傳 stderr，而不是靜默失敗。
- `backend/src/merger.py` 靜態影片產生改為等比例縮放 + padding 到 720x1280，避免圖片被硬拉伸。
- `backend/src/merger.py` concat 合併改為 `libx264` 重編碼，降低不同來源影片 codec/fps/resolution 不一致的失敗風險。
- `backend/src/pipeline.py` 新增 `sections` / `beats` 兩種切段模式，預設 `sections`，避免 API 呼叫爆量。
- `backend/src/pipeline.py` 會清理切割出的暫存音訊片段。
- `backend/src/lipsync.py` 加強對 Gradio 回傳格式的容錯，可處理路徑、URL、dict、list 等常見格式。
- `backend/src/lipsync.py` 改為 provider 架構，新增 `sadtalker_hf`，並保留 `liveportrait_hf` 作為 legacy experimental provider。
- `backend/src/lipsync.py` 新增 `wav2lip_zerogpu_hf` provider，呼叫 `image + audio -> video` 類 Wav2Lip ZeroGPU Space。
- `backend/src/pipeline.py` 改讀取 `config["lipsync"]`，不再硬編碼 LivePortrait Space。
- `backend/src/pipeline.py` 新增 `audio.max_duration_seconds` 支援，MVP 預設只取前 30 秒。
- `backend/src/merger.py` 合併時加入原始音訊 duration 作為 `-t`，避免外部模型回傳較長影片造成結尾多出無音訊片段。
- 新增 `backend/scripts/test_lipsync_space.py`，可先 `view_api()` 檢查候選 HF Space，再用短音訊做單段預測測試。
- `backend/requirements.txt` 將 `gradio_client` pin 為 `2.5.0` 以支援 Wav2Lip ZeroGPU 的 `sse_v3` protocol，並移除暫停使用的 `google-genai`。

### Video + Audio -> MuseTalk 對嘴流程實測
使用者改採新主線：**多段人物 MP4 → 去除背景音 → 合成 base MP4 → 合入 MP3 → MuseTalk 對嘴 → 最終 MP4**。

本次素材：
- `inputs/Gina-01.mp4`
- `inputs/Gina-02.mp4`
- `inputs/Gina-03.mp4`
- `inputs/Café_no_Mar.mp3`

本地 FFmpeg 產物：
- `outputs/gina_base_silent.mp4`：三段 Gina 影片去音訊後合成，30.00 秒，1280x720，24fps，無音軌。
- `outputs/gina_base_with_audio.mp4`：base silent + MP3，28.66 秒，1280x720，24fps，含 AAC 音軌。

MuseTalk endpoint：
- `trymonolith/MuseTalk`
- API：`audio_file + video_file + fps + quality -> generated_video`
- endpoint：`/generate_lipsync_video`

實測結果：
- 使用者明確同意上傳 `outputs/gina_base_with_audio.mp4` 與 `inputs/Café_no_Mar.mp3` 到 `trymonolith/MuseTalk`。
- MuseTalk prediction 成功，輸出 `outputs/gina_musetalk_final.mp4`，但該檔只有 video stream。
- 已用 FFmpeg 將原 MP3 合回 MuseTalk 輸出，產出 `outputs/gina_musetalk_final_with_audio.mp4`。
- 最終檔 `gina_musetalk_final_with_audio.mp4` 為 H.264/AAC MP4，1280x720，25fps，video 約 27.48 秒、audio 約 27.47 秒。
- 新增 `backend/scripts/run_musetalk_once.py` 作為 video+audio MuseTalk 單次測試入口。
- 使用者檢視結果後確認：`trymonolith/MuseTalk` 輸出沒有有效對嘴，且畫面持續出現物件/臉部偵測綠框。此 Space 不適合作為主線 endpoint。
- 已新增 `backend/scripts/run_wav2lip_video_once.py` 與 `generate_wav2lip_file_video()`，準備改測支援 `video_or_image + audio` 的 `manavisrani07/gradio-lipsync-wav2lip`。
- `manavisrani07/gradio-lipsync-wav2lip` 實測會產生遠端結果 `/home/user/app/results/output.mp4`，但公開檔案 URL 回傳 HTTP 403，無法下載結果；此 Space 也不適合作為主線 endpoint。
- 新檢查到 `scratchyourbrain123/MuseTalk`，API 為 `video_file + audio_file + bbox_shift -> output_video`，endpoint `/inference`。已新增 `backend/scripts/run_musetalk_bbox_once.py` 與 `generate_musetalk_bbox_video()`，等待使用者同意後可測。
- 使用者同意上傳至 `scratchyourbrain123/MuseTalk` 後實測：dict payload 回傳 `None`，path payload 觸發 upstream Gradio exception；此 Space 暫不適合作為主線 endpoint。
- 重新檢查 `Sreedesignr/MuseTalk`，API 與 `trymonolith/MuseTalk` 相同：`audio_file + video_file + fps + quality -> generated_video/status`。可作為下一個候選，但需重新取得使用者對該 Space 的上傳同意。
- 使用者同意上傳至 `Sreedesignr/MuseTalk` 後實測：prediction 成功並產出 `outputs/gina_musetalk_sreedesignr_final.mp4`，合回音訊後產出 `outputs/gina_musetalk_sreedesignr_final_with_audio.mp4`。
- 視覺檢查抽幀 `outputs/sreedesignr_frame_5s.png` 與 `outputs/sreedesignr_frame_15s.png` 顯示仍有綠色偵測框；部分片段甚至輸出 debug/mosaic layout。此 Space 同樣不適合作為主線 endpoint。
- 結論：公開 HF MuseTalk demo 多數是 debug/demo wrapper，難以取得乾淨 production 輸出。下一步應改為自管 MuseTalk/Wav2Lip endpoint（例如 Colab/FastAPI 或付費 GPU endpoint），或尋找明確關閉 debug overlay 的 API。

### Colab 自管 MuseTalk MVP 規劃
使用者確認目前素材皆為 AI 生成，授權風險相對較低；但仍需確認生成平台條款、人物相似性、音樂來源與發布平台規則。

下一步採用 **Google Colab 自管 MuseTalk**，先不做長駐 API：
- 新增 `notebooks/MV_MuseTalk_Colab.ipynb`。
- 新增 `notebooks/README.md`。
- Notebook 流程：
  1. Colab 切換 GPU runtime。
  2. Clone `TMElyralab/MuseTalk`。
  3. 依官方流程安裝 PyTorch、requirements、MMLab packages。
  4. 執行官方 `download_weights.sh` 下載模型權重。
  5. 上傳 `outputs/gina_base_with_audio.mp4` 與 `inputs/Café_no_Mar.mp3`。
  6. 將影片轉為 25fps，音訊轉為 16k WAV。
  7. 產生 MuseTalk inference config。
  8. 執行 `python -m scripts.inference` 使用 MuseTalk 1.5 權重。
  9. 若輸出無音軌，將原 MP3 合回輸出影片。
  10. 下載 `musetalk_colab_final_with_audio.mp4`。

理由：
- Colab 可直接跑官方模型與權重，不依賴公開 HF demo wrapper。
- 可以避免 debug overlay、403 下載失敗、Space 靜默錯誤等問題。
- 第一版先人工 Notebook 跑通品質，再考慮包 FastAPI/ngrok 或改到 RunPod/Vast.ai/GCP。

### Colab Install Dependencies 修正
使用者執行 Notebook 的 Install Dependencies cell 後回報錯誤。根因：
- Colab runtime 使用 Python 3.12。
- MuseTalk 官方依賴偏 Python 3.10 時代。
- `torch==2.0.1` 在指定 CUDA 11.8 index 中沒有 Python 3.12 wheel。
- `numpy==1.23.5` 無法在 Python 3.12 乾淨安裝。
- 舊 `setuptools/pkg_resources` 會引用 Python 3.12 已移除的 `pkgutil.ImpImporter`。

修正：
- `notebooks/MV_MuseTalk_Colab.ipynb` 的 Install Dependencies cell 改為安裝 Miniforge。
- 建立 `conda` 環境 `musetalk`，使用 Python 3.10。
- 所有 MuseTalk 依賴與推理改用 `conda run -n musetalk ...`。
- 推理 cell 改為 `conda run -n musetalk python -m scripts.inference ...`。
- `notebooks/README.md` 已補上錯誤原因與 fresh runtime 重跑說明。
- `frontend/src/App.jsx` 修正 React hook dependency lint 警告。

### 驗證結果
- `backend\venv\Scripts\python.exe -m py_compile ...` 通過。
- `npm.cmd run build` 通過。
- `npm.cmd run lint` 通過。

### GitHub 狀態
- 指定遠端 repo：`newesp/MV-generator`
- 遠端 repo 目前為空，預設分支 `main`。
- 本機資料夾已初始化為 Git repo，並掛上 `origin = https://github.com/newesp/MV-generator.git`。
- 尚未 commit / push。

---

## 一、專案初始需求

使用者的核心目標是開發一個 **簡易版 AI MV (Music Video) 生成器**。

| 項目 | 需求 |
|------|------|
| 語言 | Python |
| 核心流程 | 音樂分析 → 呼叫生圖/生影片 → 對嘴 → FFmpeg 合併 |
| 素材來源 | 雲端 API 生成 **+** 手動上傳（兩者並存） |
| 對嘴方案 | 在 Hugging Face 部署 LivePortrait，作為 MVP 零成本驗證 |

---

## 二、需求釐清與關鍵決策時間線

### 決策 1：LivePortrait 驅動方式
- **結論**：MVP 先在 Hugging Face 找已封裝好、支援**純音訊 (Audio/MP3)** 驅動的 LivePortrait 變體 Space。
- **後續演進**：使用者進一步提出——希望能「先生成動態影片 (MP4)，再丟給 LivePortrait 做全影片自動對嘴 (Video-to-Video)」。

### 決策 2：生圖/生影片 API 選擇
- **初始方向**：使用 Google API（Gemini / Vertex AI）。
- **轉折**：使用者確認沒有綁定計費的 GCP 專案。Google 的影片生成模型 (Veo) 強制綁定 GCP + Cloud Storage。
- **最終結論**：改用 **Fal.ai API** 作為平替方案（只需 API Key，免架 Storage，支援 Kling / Luma / Minimax 等模型）。未來有 GCP 後可切回 Google。

### 決策 3：音樂卡點分析
- **結論**：使用 Python 的 `librosa` 套件。
  - `librosa.beat.beat_track` → 萃取 BPM。
  - `librosa.onset.onset_detect` → 萃取鼓點/重音時間戳 (Timestamps) 作為畫面切換的「卡點」依據。

### 決策 4：前後端架構
- 評估了四種方案：

| 方案 | 描述 | 結果 |
|------|------|------|
| 方案 1 | FastAPI + 原生 HTML/JS/CSS | 輕量但未來擴充為 SaaS 時重寫成本高 |
| 方案 2 | Gradio / Streamlit | 最快驗證但 UI 自由度低 |
| **方案 3** | **FastAPI + Vite/React** | **✅ 採用**：為未來互動式時間軸編輯器打基礎 |
| 方案 4 | 純 CLI | 無 UI |

- **使用者最終選擇**：方案 3 (FastAPI + Vite/React)，直接以 SaaS 為目標架構。

### 決策 5：開發用模型建議
- **結論**：建議使用 Gemini 3.1 Pro 進行開發（適合複雜全端架構、多步驟推理與除錯）。

---

## 三、開源專案競品調研

### 調研結論：市面上沒有完美匹配的 All-in-One 方案，建議自行開發。

#### 使用者指定檢視的兩個專案

| 專案 | 技術棧 | 評估 |
|------|--------|------|
| [gouveags/ai-music-video-generator](https://github.com/gouveags/ai-music-video-generator) | Astro + Express + Postgres + Redis + MinIO (全端 Monorepo) | ❌ 架構太重（需資料庫、Redis）、Node.js 生態、無卡點分析、無對嘴 |
| [tanbryan/ai-mv-generator](https://github.com/tanbryan/ai-mv-generator) | Python 多智能體系統 (OpenAI GPT-4o + DALL-E 3) | ❌ 本質是「歌詞幻燈片」、無 librosa 音樂分析、無對嘴、深度綁定 OpenAI Agent 架構 |

#### 其他相關開源專案

| 專案 | 可借鏡之處 |
|------|------------|
| [mugen](https://github.com/scherroman/mugen) | librosa 節奏分析 + 自動剪輯拼接的概念（與我們的 analyzer + merger 高度相似） |
| [Glitchframe](https://github.com/OlaProeis/Glitchframe) | SDXL 生成風格化背景 + 動態文字排版 |
| [MuseTalk](https://github.com/Tencent/MuseTalk) / [Wav2Lip](https://github.com/numz/sd-wav2lip-uhq) | 成熟的純音訊對嘴方案，可作為 LivePortrait 的備選 |

---

## 四、目前已完成的程式碼

### 專案結構
```
MV-generator/
├── backend/
│   ├── configs/
│   │   └── config.yaml           # 系統設定（HF Space ID、路徑等）
│   ├── src/
│   │   ├── __init__.py
│   │   ├── analyzer.py           # ✅ librosa BPM + onset 卡點分析
│   │   ├── generator.py          # ⚠️ 本機圖片掃描可用，Google API 為空殼
│   │   ├── lipsync.py            # ⚠️ gradio_client 呼叫框架完成，參數名稱未驗證
│   │   ├── merger.py             # ✅ FFmpeg 靜態影片 + concat + 音訊切割
│   │   └── pipeline.py           # ✅ 主管線（音訊切割 → 對嘴 → fallback → 合併）
│   ├── main.py                   # ✅ FastAPI 伺服器（/upload, /generate, /status, /download）
│   ├── requirements.txt          # ✅ 已安裝（librosa, gradio_client, fastapi, google-genai 等）
│   └── venv/                     # ✅ Python 虛擬環境已建立
├── frontend/
│   ├── src/
│   │   ├── App.jsx               # ✅ 上傳音訊 + 圖片 + 生成 + 狀態輪詢 + 下載
│   │   └── index.css             # ✅ 暗黑主題高質感 UI
│   ├── package.json              # ✅ 依賴已安裝
│   └── vite.config.js
├── inputs/                       # 使用者上傳素材的暫存資料夾
└── outputs/                      # 最終生成成品的資料夾
```

### 各模組狀態

| 模組 | 檔案 | 狀態 | 說明 |
|------|------|------|------|
| 音樂分析 | `analyzer.py` | ✅ 完成 | librosa BPM + onset，min_gap=0.5s 過濾 |
| 圖片準備 | `generator.py` | ⚠️ 部分完成 | 本機掃描可用；Google API 為 TODO stub，需改為 Fal.ai |
| 對嘴 | `lipsync.py` | ⚠️ 框架完成 | gradio_client 連線邏輯可用，但參數名是猜測值、Space ID 未驗證 |
| 影片合併 | `merger.py` | ✅ 完成 | 靜態影片生成 + concat demuxer + 音訊切割 |
| 管線協調 | `pipeline.py` | ✅ 完成 | 串行處理，含 lipsync fallback 到 static video |
| API 伺服器 | `main.py` | ✅ 完成 | FastAPI + CORS + 背景任務 |
| 前端 | `App.jsx` | ✅ 完成 | 基本上傳/生成/下載流程 |
| 影片生成 | `video_generator.py` | ❌ 尚未建立 | Fal.ai 整合尚未實作 |

---

## 五、全面檢視：問題、風險與建議

### 🔴 P0 — 阻塞性問題 (Blocker)

#### 5.1 LivePortrait Audio-driven HF Space 尚未驗證
- **現況**：`config.yaml` 預設指向 `KwaiVGI/LivePortrait`（官方），該 Space **不支援純音訊輸入**，呼叫必定失敗。
- **更高要求**：使用者希望做 Video-to-Video 對嘴（`source_video + driving_audio → output_video`），能滿足這個組合的免費公開 Space 可能非常少。
- **影響**：整個「對嘴」功能無法運作。
- **建議**：
  1. 先去 HF Spaces 搜索並實測可用的 Audio-driven Space。
  2. 若找不到，備選方案：**MuseTalk** 或 **Wav2Lip** 的 HF Space（更成熟的純音訊對嘴方案）。
  3. 或退回「Video-driven」官方 LivePortrait：預錄一段嘴巴張合的 driving video 作為通用驅動源。

---

### 🟡 P1 — 重要問題

#### 5.2 卡點數量可能過多，導致 API 呼叫爆量
- **現況**：`analyzer.py` 的 `min_gap = 0.5` 秒，一首 3 分鐘的歌可能產生 100~200+ 個 segment。
- **影響**：每個 segment 都要呼叫 Fal.ai + LivePortrait = 200~400 次 API 呼叫，超出免費額度且耗時數小時。
- **建議**：新增「段落模式」(將歌曲分為 4~8 大段落) 與「卡點模式」(現有) 的切換機制，讓使用者在前端選擇。

#### 5.3 串行管線太慢
- **現況**：`pipeline.py` 用 `for` 迴圈逐段串行處理。
- **影響**：如果每段要等 Fal.ai (30~120s) + LivePortrait (20~60s)，一首歌可能跑數小時。
- **建議**：使用 `concurrent.futures.ThreadPoolExecutor` 或 `asyncio.gather` 並行處理，控制最大併發數 3~5。

#### 5.4 FFmpeg concat 編碼不一致風險
- **現況**：`merger.py` 使用 `-c:v copy` 做 concat。
- **影響**：如果來自 LivePortrait 的影片與 Fal.ai 生成的影片在解析度/幀率/編碼不同，會失敗或花屏。
- **建議**：在 concat 前加 normalize 步驟，統一 resolution / fps / codec，或改用 `-c:v libx264` 強制重編碼。

#### 5.5 config.yaml 使用相對路徑
- **現況**：`"../inputs"` 和 `"../outputs"` 是相對路徑。
- **影響**：在 `uvicorn --reload` 下工作目錄可能不一致，導致路徑解析錯誤。
- **建議**：在 `main.py` 中以 `os.path.dirname(__file__)` 計算絕對路徑。

---

### 🟢 P2 — 後續改善

#### 5.6 全域變數狀態管理
- `main.py` 的 `generation_status` 全域 dict 非執行緒安全，且只支援單一使用者。
- MVP 可接受，SaaS 擴展時需改為 Job Queue (Celery + Redis) 加 UUID 追蹤。

#### 5.7 generator.py 中的 Google API 空殼
- `generate_image_google_api()` 仍參考 Google API，但已決定轉向 Fal.ai。
- 需清理或重構為 Fal.ai 整合。

#### 5.8 lipsync.py 參數名稱硬編碼
- `client.predict()` 的參數名 (`source_image`, `driving_audio`) 是猜測值。
- 建議加入 `client.view_api()` debug 輸出，並將參數名放入 `config.yaml` 讓使用者可自訂。

#### 5.9 暫存檔清理不完整
- `pipeline.py` 只清理了 video_clips，切割出的 `segment_xxx.m4a` 音訊片段未清理。

#### 5.10 前端功能缺口
- 缺少：生成模式選擇 (段落/卡點)、Prompt 輸入框、分段進度顯示、API Key 設定介面。

---

## 六、建議的下一步行動順序

```
Step 1 (Blocker)
🔍 搜尋並驗證 HF 上可用的 Audio-driven LivePortrait Space
   或確認備選方案 (MuseTalk / Wav2Lip)
        │
        ▼
Step 2
🔧 更新 config.yaml（寫入驗證過的 Space ID + 參數名稱）
   修復 P1 的已知 Bug（路徑、concat 編碼、暫存檔清理）
        │
        ▼
Step 3
🎬 實作 video_generator.py（Fal.ai 影片生成模組）
        │
        ▼
Step 4
🔄 重構 pipeline.py
   新流程：圖片 → Fal.ai 生影片 → LivePortrait V2V 對嘴
   加入並行處理 + 段落模式
        │
        ▼
Step 5
🖥️ 前端擴充
   模式選擇 / Prompt 輸入 / 分段進度 / API Key 設定
        │
        ▼
Step 6
🧪 端到端整合測試
```

> **⚠️ Step 1 是阻塞項**。如果找不到可用的 Audio-driven HF Space，後續的 V2V 對嘴計畫就需要調整備選方案。建議在繼續寫程式碼前，先花時間確認這一點。
