#!/usr/bin/env python3
"""Render review images from the generator's actual FreeCAD tessellations."""
from pathlib import Path
import json
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/torabo-tenting-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors, font_manager
from matplotlib.collections import PolyCollection
from matplotlib.patches import Ellipse, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

OUT=Path(__file__).resolve().parent/'generated/battery-tenting-bar'
MESH=json.loads((OUT/'right-preview-mesh.json').read_text())
CHECK=json.loads((OUT/'validation.json').read_text())['Right']
font=Path('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc')
if font.exists():
    font_manager.fontManager.addfont(str(font))
    plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus']=False
COLORS={'housing':'#315971','lid':'#bbd4df','cover':'#70b0ca','tray':'#7bb98a','module_cage':'#acd2b1',
        'module':'#328455','switch':'#6b6d74','ptc':'#c59e43','diode':'#3e424c',
        'battery':'#eeb143','components':'#575b63','magnets':'#90969e','usb_plug':'#737b86','cable':'#303742','ties':'#444b56','tie_heads':'#444b56','door':'#70b0ca','open_door':'#70b0ca','battery_out':'#eeb143',
        'outlet_housing':'#315971','outlet_lid':'#bbd4df','outlet_cover':'#70b0ca','cable_install_stub':'#303742','cable_closure':'#bbd4df'}


def draw(ax,name,z=0,alpha=1,mesh=None,closed_stack=False):
    mesh=MESH if mesh is None else mesh
    v=np.asarray(mesh[name]['vertices'])+np.array([0,0,z])
    f=v[np.asarray(mesh[name]['triangles'])]
    if closed_stack:
        # Hide surfaces occluded by the closed cover. Matplotlib's triangle
        # depth ordering otherwise draws pocket interiors through the 0.4 mm
        # film, even though the saved BRep and STL have a closed top surface.
        axis=np.array([0,np.sin(np.deg2rad(CHECK['tenting_angle_deg'])),np.cos(np.deg2rad(CHECK['tenting_angle_deg']))])
        if name=='cover':
            plane=np.dot(axis,[0,12,CHECK['contact_center_height_mm']])
            f=f[(np.abs(f@axis-plane)<1e-5).any(axis=1)]
        elif name=='lid':
            normals=np.cross(f[:,1]-f[:,0],f[:,2]-f[:,0])
            normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
            f=f[np.abs(normals@axis)<.5]
    # Long planar faces need subdivision for correct painter-depth ordering.
    # Otherwise a whole enclosure-wall triangle can sort behind an inside post.
    done=[]
    for _ in range(24):
        edges=np.stack([np.linalg.norm(f[:,1]-f[:,0],axis=1),np.linalg.norm(f[:,2]-f[:,1],axis=1),np.linalg.norm(f[:,0]-f[:,2],axis=1)],axis=1)
        good=edges.max(axis=1)<3.0
        if good.any():done.append(f[good])
        if good.all():break
        bad=f[~good];idx=edges[~good].argmax(axis=1);rows=np.arange(len(bad))
        a=bad[rows,idx];b=bad[rows,(idx+1)%3];c=bad[rows,(idx+2)%3];mid=(a+b)/2
        f=np.concatenate([np.stack([a,mid,c],axis=1),np.stack([mid,b,c],axis=1)])
    f=np.concatenate(done)
    normals=np.cross(f[:,1]-f[:,0],f[:,2]-f[:,0])
    normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    light=np.array([-.4,-.5,1]);light/=np.linalg.norm(light)
    shade=.58+.42*np.clip(normals@light,0,1)
    rgba=np.ones((len(f),4));rgba[:,:3]=np.asarray(colors.to_rgb(COLORS.get(name,'#bdc3cb')))*shade[:,None];rgba[:,3]=alpha
    if not hasattr(ax,'cad_faces'):ax.cad_faces=[];ax.cad_colors=[]
    ax.cad_faces.append(f);ax.cad_colors.append(rgba)


def finish_mesh(ax):
    # Sort all parts' triangles together, so posts and components cannot appear through
    # an opaque enclosure just because separate collections overlap in depth.
    p=Poly3DCollection(np.concatenate(ax.cad_faces),facecolors=np.concatenate(ax.cad_colors),edgecolors='none',zsort='average',antialiased=False)
    ax.add_collection3d(p)


def holder_wire(ax,z):
    verts=np.asarray(MESH['holder']['vertices'])
    low=verts.min(axis=0)+[0,0,z];high=verts.max(axis=0)+[0,0,z]
    for axis in range(3):
        others=[i for i in range(3) if i!=axis]
        for a in [low[others[0]],high[others[0]]]:
            for b in [low[others[1]],high[others[1]]]:
                p=low.copy();q=low.copy();p[axis]=low[axis];q[axis]=high[axis]
                p[others]=[a,b];q[others]=[a,b]
                ax.plot(*np.vstack([p,q]).T,color='#8f959c',linewidth=.8,linestyle='--')


def style(ax,x,y,z,elev=26,azim=-57):
    ax.set_xlim(*x);ax.set_ylim(*y);ax.set_zlim(*z)
    ax.set_box_aspect([x[1]-x[0],y[1]-y[0],z[1]-z[0]])
    ax.view_init(elev=elev,azim=azim);ax.set_axis_off()


fig=plt.figure(figsize=(14,7.5),facecolor='#f5f7fa')
fig.suptitle('右側の単4電池テンティングバー — 内蓋1 mmと磁石カバー',fontsize=18,x=.05,ha='left',y=.96)
fig.text(.05,.895,'本体70 × 29 mm / ふた込み幅34 mm / 中央高さ %.1f mm / 傾斜 %.2f°'%(CHECK['contact_center_height_mm'],CHECK['tenting_angle_deg']),fontsize=12,color='#4c5968')
ax=fig.add_axes([.025,.13,.48,.73],projection='3d',facecolor='#f5f7fa')
for name in ['housing','lid','magnets','cover','door','usb_plug','cable']:draw(ax,name)
finish_mesh(ax)
style(ax,(-40,72),(-20,36),(-1,50),elev=32,azim=55)
ax.text2D(.06,.89,'組み立て状態',transform=ax.transAxes,fontsize=14)
fig.text(.05,.155,'右側USB-Cへの固定ケーブル\nケーブル外皮を本体で保持\nプラグ外形・線径は仮定',fontsize=11,color='#3e4b59')
ax=fig.add_axes([.50,.13,.48,.73],projection='3d',facecolor='#f5f7fa')
draw(ax,'housing');draw(ax,'door');draw(ax,'tray',z=28);draw(ax,'components',z=28);draw(ax,'module_cage',z=34);draw(ax,'ties',z=28);draw(ax,'tie_heads',z=28)
holder_wire(ax,28);draw(ax,'battery',z=28)
draw(ax,'lid',z=62);draw(ax,'magnets',z=62);draw(ax,'cover',z=75)
finish_mesh(ax)
style(ax,(-2,72),(-6,35),(-1,110),elev=23,azim=-61)
ax.text2D(.05,.89,'分解状態',transform=ax.transAxes,fontsize=14)
fig.text(.55,.155,'緑：取り外せるPLA部品トレー\n点線：電池ホルダーの収納範囲\nホルダーの開口は背面',fontsize=11,color='#3e4b59')
fig.text(.05,.055,'背面のスライドふたから電池を交換。磁石カバーのねじを外さず、配線・ホルダーを動かしません。',fontsize=10,color='#6d7785')
fig.savefig(OUT/'bar-preview.png',dpi=150);plt.close(fig)

left_mesh=json.loads((OUT/'left-preview-mesh.json').read_text())
fig=plt.figure(figsize=(14,7),facecolor='#f5f7fa')
fig.suptitle('左側は支持専用 — 電池蓋・スイッチ穴・配線穴をなくした Rev J',fontsize=18,x=.04,ha='left',y=.96)
fig.text(.04,.875,'本体70 × 29 mm / 中央高さ26.6 mm / 磁石2個 / M2×3.5 mmねじ4本 / 印刷部品3点',fontsize=11,color='#4c5968')
for i,title in enumerate(['スイッチ側：閉じた側壁','電池交換口側：一体の側壁','分解状態：電装用の固定座なし']):
    ax=fig.add_axes([.005+i*.33,.18,.33,.63],projection='3d',facecolor='#f5f7fa')
    draw(ax,'housing',mesh=left_mesh)
    for name,z in [('lid',32),('magnets',32),('cover',45)]:
        if name=='magnets' and i<2:continue
        draw(ax,name,z=z if i==2 else 0,mesh=left_mesh,closed_stack=i<2)
    finish_mesh(ax)
    style(ax,(-2,72),(-3,32),(-1,80 if i==2 else 33),elev=27,azim=58 if i==1 else -60)
    ax.text2D(.01,.96,title,transform=ax.transAxes,fontsize=12)
fig.text(.04,.085,'中空の本体と磁石用内蓋・上カバーだけ。底と側壁は一体で、電池蓋・レール・トレー・押さえは不要です。',fontsize=11,color='#4c5968')
fig.text(.04,.04,'左右の高さ・磁石位置・薄膜と共通ねじの仕様を維持。印刷後の公差・磁力・強度は実物で確認します。',fontsize=10,color='#6d7785')
fig.savefig(OUT/'left-support-preview.png',dpi=150);plt.close(fig)

fig=plt.figure(figsize=(15,6.5),facecolor='#f5f7fa')
fig.suptitle('取り外せるPLA部品トレー',fontsize=21,x=.04,ha='left',y=.95)
fig.text(.04,.87,'GB-BH-4X1-WPを横向きに固定。背面へ電池を抜き差しします。昇圧モジュールにはねじ式の押さえ。',fontsize=11,color='#4c5968')
for i,title in enumerate(['部品を載せた状態','位置決め枠・端子穴・固定穴','裏面の配線溝']):
    ax=fig.add_axes([.015+i*.328,.18,.324,.60],projection='3d',facecolor='#f5f7fa')
    draw(ax,'tray')
    if i==0:
        for name in ['module','switch','ptc','diode','battery','module_cage','ties','tie_heads']:draw(ax,name)
        holder_wire(ax,0)
    finish_mesh(ax)
    style(ax,(4,70),(0,30),(0,25),elev=-45 if i==2 else 45,azim=-63)
    ax.text2D(.05,.98,title,transform=ax.transAxes,fontsize=13)
    ax.text2D(.04,-.02,['点線：ホルダー＋電池の想定範囲\n部品寸法の一部は実測前','縦板にホルダー接点穴：55 mm間隔\nトレー固定：M2ねじをPLAへ直接','溝：幅3 × 深さ1 mm\n本体の床まで2.4 mmの空間'][i],transform=ax.transAxes,fontsize=11,color='#3e4b59')
fig.text(.04,.055,'緑の部品はPLA製の固定具です。配線は絶縁した線を使用し、PLA上ではんだ付けしません。',fontsize=11,color='#6d7785')
fig.savefig(OUT/'tray-preview.png',dpi=150);plt.close(fig)

fig=plt.figure(figsize=(15,7.5),facecolor='#f5f7fa')
fig.suptitle('背面から、ねじを外さず電池交換',fontsize=22,x=.04,ha='left',y=.95)
fig.text(.04,.875,'GB-BH-4X1-WPを横向きに固定。単4電池・既製モジュール・PLAへの直接ねじ込みを継続。',fontsize=12,color='#4c5968')
for i,title in enumerate(['閉じた状態','爪を下へ押し、ふたを横に抜く']):
    ax=fig.add_axes([.01+i*.49,.16,.49,.66],projection='3d',facecolor='#f5f7fa')
    for name in ['housing','lid','cover','tray','module_cage','components','ties','tie_heads']:draw(ax,name)
    draw(ax,'open_door' if i else 'door')
    if i:
        draw(ax,'battery_out');holder_wire(ax,0)
        ax.quiver(4,34,13,-25,0,0,color='#cb7740',arrow_length_ratio=.15,linewidth=2)
        ax.quiver(38.5,34,13.7,0,6,0,color='#cb7740',arrow_length_ratio=.3,linewidth=2)
    finish_mesh(ax)
    style(ax,(-55,72),(0,53),(-1,33),elev=27,azim=58)
    ax.text2D(.05,.93,title,transform=ax.transAxes,fontsize=14)
    ax.text2D(.05,.05,['ふたの爪で閉位置を保持\n追加のねじ・ナットは不要','ふたを取り外し、電池だけ交換\n点線：固定したホルダーの収納範囲'][i],transform=ax.transAxes,fontsize=11,color='#3e4b59')
fig.text(.04,.055,'本体の交換口：53 × 12.1 mm。レール・爪の公差と電池の着脱は、印刷品と手持ちホルダーで確認が必要です。',fontsize=11,color='#6d7785')
fig.savefig(OUT/'battery-access-preview.png',dpi=150);plt.close(fig)

fig=plt.figure(figsize=(13,7.5),facecolor='#f5f7fa')
fig.suptitle('取り付け状態の上面図 — バーと閉じたふたがケース内に収まる',fontsize=19,x=.04,ha='left',y=.95)
fig.text(.04,.87,'灰色：このリポジトリの実際の底ケース外形　青：テンティングバー　黄色：一致する磁石位置',fontsize=11,color='#4c5968')
for i,side in enumerate(['Left','Right']):
    mesh=json.loads((OUT/(side.lower()+'-preview-mesh.json')).read_text())
    check=json.loads((OUT/'validation.json').read_text())[side]
    ax=fig.add_axes([.06+i*.48,.19,.43,.60],facecolor='#f5f7fa')
    for name,color in [('keyboard_footprint','#cbd1d9'),('housing',COLORS['housing']),('lid',COLORS['lid']),('cover',COLORS['cover']),('door',COLORS['door'])]:
        if name not in mesh:continue
        vs=np.asarray(mesh[name]['vertices']);tri=vs[np.asarray(mesh[name]['triangles'])]
        ax.add_collection(PolyCollection(tri[:,:,[1,0]],facecolors=color,edgecolors='none',antialiased=False))
    for u in check['magnet_bar_u_mm']:
        ax.add_patch(Ellipse((check['magnet_line_v_mm'],u),12*np.cos(np.deg2rad(check['tenting_angle_deg'])),12,facecolor='#e9bc58',edgecolor='#8a6b32',linewidth=.7))
    ax.set_xlim(-5,134);ax.set_ylim(-7,82);ax.set_aspect('equal')
    ax.spines[['top','right']].set_visible(False)
    ax.set_title(('左側' if side=='Left' else '右側')+' / バー長さ70 mm',fontsize=14)
    ax.set_xlabel('横方向 (mm)',fontsize=10);ax.set_ylabel('奥行方向 (mm)',fontsize=10)
fig.text(.04,.085,'中央高さ%.1f mm。ケース外周を0.5 mm内側へ寄せた輪郭でも、左3部品・右6部品のはみ出し体積は0。'%CHECK['contact_center_height_mm'],fontsize=11,color='#4c5968')
fig.text(.04,.045,'CADの実形状を投影。電池交換時はふたを外へスライドします。給電ケーブルとプラグは図から省略。',fontsize=10,color='#6d7785')
fig.savefig(OUT/'keyboard-fit-preview.png',dpi=150);plt.close(fig)
fig=plt.figure(figsize=(13,7.5),facecolor='#f5f7fa')
fig.suptitle('USB-Cプラグを穴へ通さず、配線済みケーブルを組み込む',fontsize=19,x=.04,ha='left',y=.95)
fig.text(.04,.875,'Rev I：上に開いた幅4 mmの溝 ＋ 内蓋と一体の押さえ。右バーの出口付近を切り出した部分図。',fontsize=11,color='#4c5968')
for i,title in enumerate(['① 蓋を外し、ケーブルの途中を上から置く','② 内蓋の押さえで溝を閉じる']):
    ax=fig.add_axes([.015+i*.49,.19,.48,.61],projection='3d',facecolor='#f5f7fa')
    draw(ax,'outlet_housing')
    draw(ax,'cable_install_stub',z=7 if i==0 else 0)
    draw(ax,'outlet_lid',z=12 if i==0 else 0)
    draw(ax,'outlet_cover',z=12 if i==0 else 0)
    finish_mesh(ax)
    if i==0:ax.quiver(-.7,20,21.5,0,0,-5,color='#cc7740',linewidth=2,arrow_length_ratio=.25)
    style(ax,(-3,10),(14,26),(10,40),elev=25,azim=-145)
    ax.text2D(.015,.99,title,transform=ax.transAxes,fontsize=12)
fig.text(.04,.115,'端子・昇圧部品はケーブルの両端につけたまま。内部の台座と結束バンドで外皮を保持します。',fontsize=11,color='#4c5968')
fig.text(.04,.07,'外径3 mmを仮定。組立の連続経路は半径に0.15 mmの余裕を加えて干渉なし。実物の線径・印刷公差は要確認。',fontsize=10,color='#6d7785')
fig.savefig(OUT/'cable-access-preview.png',dpi=150);plt.close(fig)
fig=plt.figure(figsize=(13,6.5),facecolor='#f5f7fa')
fig.suptitle('内蓋1 mmと浅い磁石穴 — 上カバーの膜も薄くして距離を縮める',fontsize=18,x=.04,ha='left',y=.96)
fig.text(.04,.875,'寸法は接触面に垂直な方向。厚み方向を拡大した断面模式図。灰：キーボード　青：上カバー　緑：内蓋。',fontsize=11,color='#4c5968')
old_cos=np.cos(np.deg2rad(12.932299337117003))
states=[('Rev H',1.2*old_cos,old_cos,.5*old_cos,.8),
        ('Rev I',CHECK['inner_lid_thickness_vertical_mm']*np.cos(np.deg2rad(CHECK['tenting_angle_deg'])),
         CHECK['cover_thickness_vertical_mm']*np.cos(np.deg2rad(CHECK['tenting_angle_deg'])),
         CHECK['cover_magnet_skin_normal_mm'],CHECK['magnet_pocket_depth_normal_mm'])]
for i,(title,inner,upper,skin,pocket) in enumerate(states):
    ax=fig.add_axes([.04+i*.49,.26,.44,.53],facecolor='#f5f7fa')
    def rect(x,y,w,h,color):
        ax.add_patch(Rectangle((x,y),w,h,facecolor=color,edgecolor='#71808b',linewidth=.7))
    rect(-9,0,18,.5,'#cbd1d9')
    rect(-6,.5,12,1,'#89929d')
    ax.text(0,1,'ケース側の磁石',ha='center',va='center',fontsize=11,color='white')
    ax.text(0,.25,'ケース側の底 0.5 mm',ha='center',va='center',fontsize=9)
    for x in [-9,6.5]:rect(x,-upper,2.5,upper,COLORS['cover'])
    rect(-6.5,-skin,13,skin,COLORS['cover'])
    rect(-9,-upper-inner,18,inner-pocket,COLORS['tray'])
    for x in [-9,6.125]:rect(x,-upper-pocket,2.875,pocket,COLORS['tray'])
    rect(-6,-skin-1,12,1,'#eeb143')
    ax.text(0,-skin-.5,'バー側の磁石',ha='center',va='center',fontsize=11)
    ax.add_patch(Rectangle((-6,-upper-pocket),12,1,facecolor='none',edgecolor='#615745',linewidth=1.5,linestyle='--'))
    ax.annotate('',xy=(7.5,.5),xytext=(7.5,-skin),arrowprops={'arrowstyle':'<->','color':'#9b6934','linewidth':1.3})
    ax.text(8.1,(.5-skin)/2,'磁石間\n%.2f mm'%(.5+skin),ha='left',va='center',fontsize=10,color='#79522c')
    ax.set_xlim(-9.5,11.9);ax.set_ylim(-2.6,1.75);ax.set_axis_off()
    ax.set_title(title,fontsize=15)
    ax.text(.01,-.09,'内蓋 %.1f mm / 磁石穴 %.2f mm / 膜 %.1f mm'%([1.2,1.0][i],pocket,[.5,.4][i]),transform=ax.transAxes,fontsize=11)
    ax.text(.01,-.19,'磁石穴の底 %.2f mm / 上下の遊び %.2f mm'%(inner-pocket,upper-skin+pocket-1),transform=ax.transAxes,fontsize=10,color='#4c5968')
fig.text(.04,.085,'黄：カバー裏面へ引き寄せられた位置　破線：内蓋の穴の底へ置いた位置。距離を縮める効果は上カバーの膜の薄肉化によるもの。',fontsize=10,color='#4c5968')
fig.text(.04,.04,'FreeCADで検証した設計寸法。磁力の増加量・膜の強度・印刷公差は実物で確認します。',fontsize=10,color='#6d7785')
fig.savefig(OUT/'magnet-section-preview.png',dpi=150);plt.close(fig)
print('Saved right bar, left support, tray, battery-access, keyboard-fit, cable-access and magnet-section previews')
