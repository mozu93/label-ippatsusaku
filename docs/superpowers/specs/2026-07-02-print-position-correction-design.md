# 宛名ラベル印刷位置補正 設計書

**作成日:** 2026-07-02
**対象バージョン:** v1.3.13（予定）

---

## 1. 概要

姉妹アプリ `cci-billing-label`（https://github.com/mozu93/cci-billing-label）で実施された
「宛名ラベル印刷位置の補正」を本アプリに移植する。

移植元の変更は以下4コミットで構成されていた:

1. `_draw_label` にクリップパスを追加（ラベル枠外へのテキストはみ出し防止）
2. クリップに加え、セルを内側に安全余白（水平3mm・垂直2mm）分縮小してから描画する方式に変更
3. 実機印刷テストの結果、水平安全余白を3mm→5mmに拡大
4. 設定画面にレイアウトごとの印刷位置補正（横・縦オフセット、ユーザー調整可能）を追加

本アプリでは、上記の集大成である「クリップ＋安全余白（水平5mm・垂直2mm）＋ユーザー調整可能な印刷位置補正」を全て移植する。ただし以下の点で移植先の実情に合わせて変更する:

- 設定UIは移植元の「設定タブ」ではなく、**ファイルメニューの「印刷位置補正...」項目**から開くダイアログとする（本アプリはタブ形式の設定画面を持たないため）
- 設定値の永続化は、移植元の独自JSON設定（`app_config.py`）ではなく、**本アプリが既に使用している `QSettings("mozu93", "label-ippatsusaku")`** に統一する
- **卓上プレート（`split4` モード）は対象外**とする。理由: `split4` はシール用紙ではなくA4用紙に直接印刷する形式で、大きな文字を目一杯のレイアウトで描画する設計のため、安全余白による縮小がデザインを崩す。また直近追加した裁断ガイド機能（`docs/superpowers/specs/2026-07-02-plate-cut-guide-design.md`）はA4用紙の絶対座標を前提としており、印刷位置補正の対象にしない。

---

## 2. 仕様詳細

### 2.1 クリップパス（全モード共通）

`_draw_label` 内で、モード分岐の前に以下を追加する:

```python
clip = c.beginPath()
clip.rect(x0, y0, w, h)
c.clipPath(clip, stroke=0, fill=0)
```

対象: `normal` / `no_person` / `nametag` / `simple` / `split4` の全モード。
（クリップ自体はラベル枠内に描画を封じ込めるだけなので、`split4` を含めても既存デザインに影響しない）

### 2.2 安全余白（normal/no_person/nametag/simple のみ）

`_draw_label` 内、クリップパス設定後に以下の定数を用いてセルを縮小する:

```python
_SAFETY_H = 5.0 * mm   # 水平安全余白（左右各5mm）
_SAFETY_V = 2.0 * mm   # 垂直安全余白（上下各2mm）
```

`normal` / `no_person` / `nametag` / `simple` の4モードは、縮小後の座標
（`xs = x0 + _SAFETY_H`, `ys = y0 + _SAFETY_V`, `ws = w - 2*_SAFETY_H`, `hs = h - 2*_SAFETY_V`）
を各描画関数に渡す。`split4` モードは対象外とし、従来通り `x0, y0, w, h` をそのまま渡す。

### 2.3 印刷位置補正（オフセット）

`generate_label_pdf()` に以下のパラメータを追加する:

```python
offset_h_mm: float = 0.0
offset_v_mm: float = 0.0
```

`_label_origin()` 内で `margin_left_mm` / `margin_top_mm` に加算する:

```python
ml = (layout.margin_left_mm + offset_h_mm) * mm
mt = (layout.margin_top_mm  + offset_v_mm) * mm
```

`split4`（`a4_4split` レイアウト）選択時は、呼び出し側が常に `offset_h_mm=0.0, offset_v_mm=0.0`
を渡す（補正を無効化する）。

### 2.4 設定の永続化（QSettings）

キー命名規則: `label_offset/{layout_key}/h_mm`, `label_offset/{layout_key}/v_mm`

対象レイアウトキー: `a_one_28185`, `a_one_28187`, `a_one_51002`（`a4_4split` は対象外）

未設定時のデフォルト値: `0.0`（現状と同じ印刷位置のまま）

補正値の範囲: -15.0 〜 15.0mm、0.5mm刻み（移植元と同一）

### 2.5 UI：ファイルメニュー「印刷位置補正...」

`app/ui/main_window.py` の `_setup_menu()` に新規「ファイル」メニューを追加し、
「ヘルプ」メニューより前（左側）に配置する。メニュー項目「印刷位置補正...」を
クリックすると新規ダイアログ `PrintOffsetDialog`（`app/ui/print_offset_dialog.py` に新規作成）
を開く。

ダイアログ仕様（CLAUDE.mdのダイアログサイズ制約に準拠）:
- 幅: 480px、高さ: 400px（`setFixedSize` 等で固定。780×600px制約を満たす）
- 説明文（移植元と同内容）:
  「印刷後にシールと印刷位置がずれる場合に補正します。
  内容が右にずれる → 横補正を負に　内容が左にずれる → 横補正を正に
  内容が下にずれる → 縦補正を負に　内容が上にずれる → 縦補正を正に」
- 対象3レイアウトそれぞれについて、`QGroupBox`（レイアウト名をタイトルに）内に
  「横補正」「縦補正」の `QDoubleSpinBox`（範囲-15.0〜15.0、刻み0.5、小数点1桁、単位mm表示）
- 「保存」ボタンでQSettingsに書き込み、保存完了メッセージを表示してダイアログを閉じる

### 2.6 PDF生成呼び出し箇所への反映

`app/ui/direct_label_dialog.py` の2箇所（プレビュー生成・PDF保存）で、
`generate_label_pdf()` 呼び出し前に選択中の `layout_key` に対応する補正値を
QSettingsから読み込み、`layout_key == "a4_4split"` の場合は `0.0, 0.0` を渡す。

---

## 3. 実装方針

**対象ファイル:**
- 修正: `app/services/label_pdf_service.py`（クリップパス・安全余白・オフセットパラメータ追加）
- 修正: `app/ui/main_window.py`（ファイルメニュー新設）
- 新規: `app/ui/print_offset_dialog.py`（印刷位置補正ダイアログ）
- 修正: `app/ui/direct_label_dialog.py`（PDF生成2箇所でオフセット読み込み・受け渡し）

---

## 4. テスト

- `tests/test_label_pdf_service.py` に以下を追加:
  - `offset_h_mm` / `offset_v_mm` を指定した場合、`normal` モードのラベル原点が
    指定分だけ移動することを確認するテスト
  - 安全余白によって `normal` モードの描画内容がラベル枠（クリップ）内に収まること
    （クリップパスの存在、またはテキスト描画位置が安全余白の内側にあること）を確認するテスト
  - `split4` モードでは、`offset_h_mm`/`offset_v_mm` を指定してもラベル原点が
    変化しない（無効化される）ことを確認するテスト
- QSettingsの読み書きは薄いラッパー関数として実装し、単体テストを追加する

---

## 5. 影響範囲

- 既存の `normal` / `no_person` / `nametag` / `simple` モードは、安全余白により
  実際の印字可能領域がひとまわり小さくなる（レイアウトによっては1行の折り返し数が
  変わる可能性がある）。既存の自動フォントサイズ調整ロジックはそのまま機能する。
- `split4`（卓上プレート）モードは描画内容・レイアウトともに変更なし。
- 補正値のデフォルトは0.0のため、設定を変更しない限り印刷結果は現状と同じ位置になる。
- DBスキーマへの影響なし。
