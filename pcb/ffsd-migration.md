# FFSD左右間接続の設計記録

既製ケーブルは Samtec `FFSD-06-D-10.00-01-N`（2×6極、254 mm、標準の両端付き）を採用する。基板側は手はんだ可能なスルーホール `FTSH-106-01-L-D-K` を左右に1個ずつ使用する。両方を上面の縦挿しとし、ストレートケーブルに合わせて左右の**同番号端子に同じ信号**を割り当てる。

| 端子 | 左の信号 | 右の信号 |
| ---: | --- | --- |
| 1 | LROW2 | LROW2 |
| 2 | COL4 | COL4 |
| 3 | LROW0 | LROW0 |
| 4 | LROW1 | LROW1 |
| 5 | COL5 | COL5 |
| 6 | COL6 | COL6 |
| 7 | COL3 | COL3 |
| 8 | COL2 | COL2 |
| 9 | COL1 | COL1 |
| 10 | GND | GND |
| 11 | LROW3 | LROW3 |
| 12 | COL0 | COL0 |

基板側は `Library.pretty/Samtec_FTSH-106-01-L-D-K.kicad_mod` を使用する。Samtec の [FTSH製品図面](https://suddendocs.samtec.com/prints/ftsh-1xx-xx-xxx-d-xx-mkt.pdf) に従い、端子ピッチ1.27 mm、-K樹脂外形5.08 × 7.54 mm とした。穴径0.71 mmは Samtec の [推奨PCBレイアウト](https://suddendocs.samtec.com/prints/fts-dth.pdf) に基づく。ランド外径1.11 mmで片側の環状銅幅0.20 mmを確保し、マスク開口はランドと同寸にして隣接開口間0.16 mmとした。[JLCPCBのPTH環状銅幅・マスクブリッジ仕様](https://jlcpcb.com/capabilities/Capab)に合わせた。表面実装ではなくスルーホールで手はんだを想定する。

左J101は (123.2, 70.0) mm、右J202は (52.0, 151.0) mm を中心に、ともにF.Cu側、回転0°で実装する。ヘッダを上から差し込み、右側ではXIAO下部に置く。ケーブルは Samtec の標準 `FFSD-06-D-10.00-01-N` とし、`-RW`（Reverse Wiring）や `-R`（Reversed）型は使わない。左右の同番号ピンへ同じ信号を割り当てている。通電前に製品サンプルで12極の同番号導通、隣接間短絡、筐体内のキーとケーブル取り回しを確認する。

[FTSH-106-01-L-D-K の製品仕様](https://www.digikey.com/en/products/detail/samtec-inc/FTSH-106-01-L-D-K/7433351)では、はんだ側ポスト長は2.29 mm。基板厚1.6 mmを差し引いた裏面側の公称突き出しは約0.69 mmで、約3 mmの裏面空間に対し余裕がある。実際にははんだフィレットの高さもあるため、組立試作で確認する。

2026-09-23 のKiCad DRCでは、左右単体および結合パネルとも未接続0、短絡・クリアランス違反0。既存設計由来のシルク被りや不要な短い銅箔等の警告は残る。`replace_phd_with_ffsd.py` は設計過程の試行用スクリプトであり、製造時は正本PCBと `jlcpcb/output/` を使用する。
