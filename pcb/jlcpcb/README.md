# JLCPCB発注データ

`bash pcb/jlcpcb/generate.sh` をリポジトリのルートで実行すると、`output/` に左右それぞれのGerber ZIP、BOM、CPL、DRCレポートに加え、左右を1回のPCBA注文にまとめるカスタマーパネルを生成します。

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

- JLCPCB実装: 1N4148Wダイオード、0603/0805抵抗・コンデンサ、XCL103D503CR-G（左）、XC8111AA01MR-G（左右）
- 手はんだ: XIAO nRF52840 Plus、AE-XCL103-5V0（右）、GB-BH-4X1-WP、ISH-1260-HA-G、Chocソケット、FFC変換基板

BOM/CPLは基板フットプリントの`exclude_from_bom`、`exclude_from_pos_files`および`LCSC`フィールドから生成します。JLCPCBへのアップロード後は、部品の向きと当日在庫をプレビュー画面で必ず確認してください。特にXCL103D503CR-Gは流通在庫が少ない場合があります。

KiCad 10のCLIはゾーンを含む結合パネルに対するDRC／Gerber出力で異常終了する場合があるため、結合GerberはKiCadのPython APIで生成します。左右の正本PCBには、パネル化の前に通常のCLI DRCを実行します。

## 回路図の再生成

左右の回路図はPCBを正として生成しています。PCBのパッド／ネットを変更した後は、KiCad付属Pythonで`pcb/generate_schematic_from_pcb.py <board> <output schematic> <left|right>`を実行し、親回路図に対してERCとネットリスト照合を行ってください。
