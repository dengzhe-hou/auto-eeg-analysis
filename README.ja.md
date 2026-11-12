<div align="center">

# Auto EEG Analysis

**EEG解析の手順を、エージェントと共有する。**

[English](README.md) · [简体中文](README.zh-CN.md) · **日本語**

[Website](https://dengzhe-hou.github.io/Auto-EEG-Analysis/index.ja.html) · [ドキュメント](docs/GETTING_STARTED.md) · [PyPI package](https://pypi.org/project/auto-eeg-analysis/0.3.3/) · [EEGLAB 0.1.3](docs/EEGLAB.md) · [Zenodo](https://doi.org/10.5281/zenodo.24012489)

</div>

AEAはコーディングエージェント向けの **22の解析スキルと10のレシピ** を提供します。研究者が科学的な計画を承認し、エージェントが手順を読んで利用者の環境でコードを実行します。スクリプト、結果、図、レビュー記録を保存します。

[クイックスタート](#quickstart) · [ライブラリを見る](#library) · [検証範囲](#validation) · [貢献する](#contributing)

[![N400 results from 20 ERP CORE participants](docs/assets/n400-example.png)](docs/EXAMPLES.md#erp-core-complete-n400-recipe-case)

ERP COREの20名分を使う固定チュートリアルです。CPz/Cz/Pz ERPの陰影は参加者間の±1 SEM、振幅の窓は300–500 msです。ICAを使わず、エージェント実行例とは別に記録しています。

[保存結果から作図](docs/EXAMPLES.md#replot-the-saved-results) · [チュートリアルを実行](docs/EXAMPLES.md#erp-core-complete-n400-recipe-case) · [エージェント実行例](docs/EXAMPLES.md#adapt-a-recipe-to-your-study)

<a id="quickstart"></a>
## クイックスタート

PyPIパッケージから、AEAリソースを含む新しいプロジェクトを作成します。Python 3.10以降と既存のMNE環境が必要です。標準パッケージは解析用の依存関係をインストールしません。

```sh
python -m pip install auto-eeg-analysis==0.3.3
aea-eeg init ./my-eeg-study --agent codex
cd my-eeg-study
codex
```

対応データをmy-eeg-study/raw/に置き、そのプロジェクトでログイン済みクライアントを起動します。パラダイムに合うレシピを選び、計算前に解析計画を承認してください。

```text
$eeg-recipe n400-semantic --data .
```

Claude Code → `--agent claude`, `claude`, `/eeg-recipe n400-semantic --data .`

[導入と依存関係の説明](docs/GETTING_STARTED.md) · [監査段階のレビュー用モデルを設定してください。](docs/GETTING_STARTED.md#configure-the-reviewer)

### 利用経路を選ぶ

| | |
| --- | --- |
| **Python / MNE** | PyPIパッケージでプロジェクトを作成、またはGitソースを利用。 [ドキュメント](docs/PACKAGES.md) |
| **MATLAB / EEGLAB** | EEGLAB拡張またはMATLABツールボックスのプレビュー版を導入。 [ドキュメント](docs/EEGLAB.md) |
| **モデルアカウントなし** | 保存配列から作図、または固定N400チュートリアルを実行。 [ドキュメント](docs/EXAMPLES.md#replot-the-saved-results) |

EEGLABの拡張マネージャーでAEA 0.1.3を導入するか、MATLABツールボックスのプレビュー版を利用できます。MATLABネイティブ経路は、既存エポックから明示したERP平均値を計算します。より広いライブラリは主にMNE-Pythonを使います。

[Windowsで最初のレポート](docs/WINDOWS_FIRST_RUN.md) · [MATLABネイティブ経路の範囲](docs/MATLAB_NATIVE.md) · [FieldTrip](https://www.fieldtriptoolbox.org/extensions/) · [File Exchange](https://www.mathworks.com/matlabcentral/fileexchange/185187-aea-for-matlab-and-eeglab)

<a id="library"></a>
## ライブラリを見る

### 10 レシピ

| レシピ | 解析 | Status |
| --- | --- | --- |
| [ern-flankers](recipes/ern-flankers/RECIPE.md) | N2、反応関連陰性電位、前頭部シータ | 検証済み |
| [mmn-oddball](recipes/mmn-oddball/RECIPE.md) | 聴覚ミスマッチ陰性電位 | 検証済み |
| [p300-oddball](recipes/p300-oddball/RECIPE.md) | 低頻度標的に対するP300 | 実験段階 群レベルの検証結果を記録済み |
| [n170-faces](recipes/n170-faces/RECIPE.md) | 顔と顔以外の対照刺激 | 検証済み |
| [n170-face-inversion](recipes/n170-face-inversion/RECIPE.md) | 正立顔と倒立顔 | 実験段階 |
| [n400-semantic](recipes/n400-semantic/RECIPE.md) | 意味プライミング | 検証済み |
| [alpha-attention-cueing](recipes/alpha-attention-cueing/RECIPE.md) | 後部アルファ活動の変調 | 実験段階 |
| [resting-microstate](recipes/resting-microstate/RECIPE.md) | 安静時のマイクロステートマップと動態 | 検証済み |
| [resting-spectral-connectivity](recipes/resting-spectral-connectivity/RECIPE.md) | パワースペクトル、非周期成分のフィット、結合性 | 検証済み |
| [complexity-anesthesia](recipes/complexity-anesthesia/RECIPE.md) | 連続信号の複雑性とエントロピー | 検証済み 覚醒状態を確認済み。ここでは麻酔状態は未検証 |

レシピの状態と検証は、各ソースに記録された設定に適用されます。 [レシピ一覧](recipes/README.md)

### 22 スキル

| | |
| --- | --- |
| データと準備 | [eeg-bids](skills/eeg-bids/SKILL.md) · [eeg-qc](skills/eeg-qc/SKILL.md) · [eeg-preprocess](skills/eeg-preprocess/SKILL.md) · [eeg-ica](skills/eeg-ica/SKILL.md) · [eeg-epoch](skills/eeg-epoch/SKILL.md) |
| ERPと時間周波数 | [eeg-erp](skills/eeg-erp/SKILL.md) · [eeg-tfr](skills/eeg-tfr/SKILL.md) |
| 連続信号 | [eeg-spectral](skills/eeg-spectral/SKILL.md) · [eeg-connectivity](skills/eeg-connectivity/SKILL.md) · [eeg-microstate](skills/eeg-microstate/SKILL.md) · [eeg-complexity](skills/eeg-complexity/SKILL.md) · [eeg-source](skills/eeg-source/SKILL.md) |
| 統計と行動 | [eeg-stats](skills/eeg-stats/SKILL.md) · [eeg-group-compare](skills/eeg-group-compare/SKILL.md) · [eeg-decoding](skills/eeg-decoding/SKILL.md) · [eeg-behavior](skills/eeg-behavior/SKILL.md) |
| 出力とレビュー | [eeg-figure](skills/eeg-figure/SKILL.md) · [eeg-methods-text](skills/eeg-methods-text/SKILL.md) · [eeg-report](skills/eeg-report/SKILL.md) · [eeg-audit](skills/eeg-audit/SKILL.md) |
| 実行の統括 | [eeg-pipeline](skills/eeg-pipeline/SKILL.md) · [eeg-recipe](skills/eeg-recipe/SKILL.md) |

<a id="validation"></a>
## 検証範囲

主なバックエンドはMNE-Pythonです。EEGLABとFieldTripは独立した比較と一部の代替経路を提供します。認証は検証範囲に記録された出力と設定に適用されます。

[検証範囲](docs/CERTIFICATION_LEVELS.md) · [Benchmark](https://github.com/dengzhe-hou/Auto-EEG-Analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/docs/BENCHMARK.md) · [研究資料アーカイブ](https://doi.org/10.5281/zenodo.24012489) · [再実行の手順](docs/REPLAY.md)

<a id="contributing"></a>
## 貢献する

レシピの追加、スキルの改善、チュートリアルの共有、初回実行の報告を歓迎します。検証要件と貢献の扱いはガイドを参照してください。

[貢献ガイド](CONTRIBUTING.md) · [初回実行を報告](https://github.com/dengzhe-hou/Auto-EEG-Analysis/issues/new?template=first-run-platform-feedback.md) · [質問と不具合](https://github.com/dengzhe-hou/Auto-EEG-Analysis/issues)

## 利用したバージョンを引用

AEAのソフトウェア版またはコミットと、元の手法・データセットを引用してください。Zenodoは2026年11月6日に固定したリソースと検証記録のアーカイブです。

[ソフトウェアの引用情報](CITATION.cff) · [パッケージとバージョン](docs/PACKAGES.md#public-versions-and-archives)

詳しい利用手順は英語で維持しています。他言語のコミュニティチュートリアルも歓迎します。

[MIT](LICENSE) · Recipe metadata CC BY 4.0 · Built on [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)
