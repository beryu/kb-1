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

見積画面では`Different Design: 2`、`Delivery Format: Panel by Customer`、`PCB Color: White`、`Silkscreen: Black`、`PCBA Type: Standard`を選択します。実装対象のダイオード48個はすべて裏面配置なので、`Assembly Side: Bottom Side`を選択してください。BOM確認画面のファイル形式は`Complete File`を選択してください。ハンドリングレールとフィデューシャルは`Added by JLCPCB`のままとします。

このパネルは左右のPCBを2 mm間隔で縦に配置し、3か所のマウスバイトタブで連結する生成物です。レール追加前の外形範囲は約128.6 x 150.2 mmです。左右別々のファイルは、個別発注や診断用として引き続き生成します。

左右間の3か所のタブには直径0.5 mmのマウスバイト穴を両端に8個ずつ設け、穴の間の残り幅を約0.36 mmにしています。切断線を基板側に0.2 mm寄せているため、折った後の突起を抑えられます。ただしマウスバイトの細かな凹凸は残るため、外形を完全に平滑にするには分離後の軽い仕上げが必要です。JLCPCBの標準Vカットはパネル全幅を通る直線に限られ、この2 mmの隙間をまたぐ局所的な3本のタブだけには適用できません。

## ネジ用の逃げ

左右の基板に各4か所、合計8か所の円弧状の逃げを`Edge.Cuts`で設けています。元の`MountingHole_5mm`フットプリントは中心が基板外にあり、基板外形を切り欠かないままパネル化で一部が落ちていました。修正後は実際の基板外形がネジ位置を避けます。生成時に8か所の外形とネジ中心の距離を検査します。

修正前にアップロードしたGerberのJLCPCBプレビューにはこの逃げが反映されません。発注には再生成した`output/combined-gerbers.zip`をアップロードし、プレビューで8か所の円弧状の切り欠きを確認してください。

## ビア寸法

左右基板と結合パネルの全ビアは、穴径0.3 mm以上・外径0.5 mm以上です。JLCPCB見積画面の`Min via hole size/diameter`は標準の`0.3mm/(0.4/0.45mm)`を選択できます。生成時に全ビアの寸法を検査します。旧Gerberには0.2 mmと0.25 mmの穴があるため、必ず新しい`combined-gerbers.zip`をアップロードしてください。

## PCBA対象

- JLCPCB実装: 1N4148Wダイオード
- 手はんだ: 右側XIAO nRF52840 Plus、左右のSamtec FTSH-106-01-L-D-K（上面からFFSDケーブルを挿入）、Chocソケット、FFC変換基板

BOM/CPLは基板フットプリントの`exclude_from_bom`、`exclude_from_pos_files`および`LCSC`フィールドから生成します。JLCPCBへのアップロード後は、ダイオードの向きと当日在庫をプレビュー画面で必ず確認してください。

結合GerberはJLCPCBの基板外形認識と整合するKiCad CLIで生成します。左右の正本PCBには、パネル化の前に通常のCLI DRCを実行します。

## 回路図の再生成

左右の回路図はPCBを正として生成しています。PCBのパッド／ネットを変更した後は、KiCad付属Pythonで`pcb/generate_schematic_from_pcb.py <board> <output schematic> <left|right>`を実行し、親回路図に対してERCとネットリスト照合を行ってください。
