# JLCPCB発注データ

Samtec FTSH-106-01-L-D-Kを左右とも上面に縦挿しする基板から生成します。左J101と右J202はともに0°で、標準の両端FFSDケーブルに合わせて同番号端子へ同じ信号を割り当てています。左右ともKiCad DRCで未接続0件、短絡・クリアランス違反0件です。製造発注前に警告内容、ケーブルの実物結線、筐体内の高さ・取り回しを確認してください。

## 左右間ケーブル

既製の Samtec `FFSD-06-D-10.00-01-N`（2×6極、254 mm、標準両端ソケット）を使用します。`-RW`または`-R`型は使用しません。左J101→右J202は同番号対応です。

| 左J101 | 右J202 | 信号 |
| ---: | ---: | --- |
| 1 | 1 | LROW2 |
| 2 | 2 | COL4 |
| 3 | 3 | LROW0 |
| 4 | 4 | LROW1 |
| 5 | 5 | COL5 |
| 6 | 6 | COL6 |
| 7 | 7 | COL3 |
| 8 | 8 | COL2 |
| 9 | 9 | COL1 |
| 10 | 10 | GND |
| 11 | 11 | LROW3 |
| 12 | 12 | COL0 |

組み立て前に実物のケーブルで上記12組の導通と隣接ピン間の短絡がないことを確認してください。特にGND（10→10）の誤接続は通電前に確認します。

`bash pcb/jlcpcb/generate.sh` をリポジトリのルートで実行すると、`output/` に左右それぞれのGerber ZIP、BOM、CPL、DRCレポートに加え、左右を1回のPCBA注文にまとめるカスタマーパネルと`combined-drc.txt`を生成します。左右とパネルの電気的DRCエラーまたは未接続が1件でもある場合は生成を中断します。

結合パネルの生成にはKiKit 1.8.0が必要です。KiCad付属Pythonへ次のようにインストールしてください。

```sh
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
  -m pip install --user -r pcb/jlcpcb/requirements-panel.txt
```

JLCPCBでは次の結合ファイルを使用します。

- PCB: `output/combined-gerbers.zip`
- BOM: `output/combined-bom.csv`
- CPL: `output/combined-cpl.csv`

見積画面では`Different Design: 2`、`Delivery Format: Panel by Customer`、`PCB Color: White`、`Silkscreen: Black`、`PCBA Type: Standard`、`Assembly Side: Both Sides`を選択します。BOM確認画面のファイル形式は`Complete File`を選択してください。ハンドリングレールとフィデューシャルは`Added by JLCPCB`のままとします。

このパネルは左右の元PCBを変更せず、2 mm間隔で縦に配置し、3か所のマウスバイトタブで連結する生成物です。JLCPCBで認識される基板寸法は約150.1 x 138.8 mmで、Standard PCBA用の5 mmレール追加後は約150.1 x 148.8 mmです。左右別々のファイルは、個別発注や診断用として引き続き生成します。

## PCBA対象

- JLCPCB実装: 1N4148Wダイオード
- 手はんだ: 右側XIAO nRF52840 Plus、左右のSamtec FTSH-106-01-L-D-K（上面からFFSDケーブルを挿入）、Chocソケット、FFC変換基板

BOM/CPLは基板フットプリントの`exclude_from_bom`、`exclude_from_pos_files`および`LCSC`フィールドから生成します。JLCPCBへのアップロード後は、ダイオードの向きと当日在庫をプレビュー画面で必ず確認してください。

結合GerberはJLCPCBの基板外形認識と整合するKiCad CLIで生成します。左右の正本PCBには、パネル化の前に通常のCLI DRCを実行します。

## 回路図の再生成

左右の回路図はPCBを正として生成しています。PCBのパッド／ネットを変更した後は、KiCad付属Pythonで`pcb/generate_schematic_from_pcb.py <board> <output schematic> <left|right>`を実行し、親回路図に対してERCとネットリスト照合を行ってください。
