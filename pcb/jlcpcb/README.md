# JLCPCB発注データ

`bash pcb/jlcpcb/generate.sh` をリポジトリのルートで実行すると、`output/` に左右それぞれのGerber ZIP、BOM、CPL、DRCレポートを生成します。

## PCBA対象

- JLCPCB実装: 1N4148Wダイオード、0603/0805抵抗・コンデンサ、XCL103D503CR-G（左）、XC8111AA01MR-G（左右）
- 手はんだ: XIAO nRF52840 Plus、AE-XCL103-5V0（右）、GB-BH-4X1-WP、ISH-1260-HA-G、Chocソケット、FFC変換基板

BOM/CPLは基板フットプリントの`exclude_from_bom`、`exclude_from_pos_files`および`LCSC`フィールドから生成します。JLCPCBへのアップロード後は、部品の向きと当日在庫をプレビュー画面で必ず確認してください。特にXCL103D503CR-Gは流通在庫が少ない場合があります。

## 回路図の再生成

左右の回路図はPCBを正として生成しています。PCBのパッド／ネットを変更した後は、KiCad付属Pythonで`pcb/generate_schematic_from_pcb.py <board> <output schematic> <left|right>`を実行し、親回路図に対してERCとネットリスト照合を行ってください。
