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
        'battery':'#eeb143','components':'#575b63','magnets':'#90969e','usb_plug':'#737b86','cable':'#303742','ties':'#444b56','tie_heads':'#444b56','door':'#70b0ca','open_door':'#70b0ca','battery_out':'#eeb143'}


def draw(ax,name,z=0,alpha=1):
    v=np.asarray(MESH[name]['vertices'])+np.array([0,0,z])
    f=v[np.asarray(MESH[name]['triangles'])]
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
fig.suptitle('kb-1  単4電池テンティングバー — PLA部品トレー Rev E',fontsize=20,x=.05,ha='left',y=.96)
fig.text(.05,.895,'本体100 × 28 mm / ふた込み幅33 mm / 中央高さ %.0f mm / 傾斜 %.2f°'%(CHECK['contact_center_height_mm'],CHECK['tenting_angle_deg']),fontsize=12,color='#4c5968')
ax=fig.add_axes([.025,.13,.48,.73],projection='3d',facecolor='#f5f7fa')
for name in ['housing','lid','magnets','cover','door','usb_plug','cable']:draw(ax,name)
finish_mesh(ax)
style(ax,(-50,102),(-20,35),(-1,50),elev=32,azim=55)
ax.text2D(.06,.89,'組み立て状態',transform=ax.transAxes,fontsize=14)
ax.text2D(.05,.10,'USB-Cオスの固定ケーブルを追加\nケーブル外皮を本体で保持\nプラグ外形・線径は仮定',transform=ax.transAxes,fontsize=11,color='#3e4b59')
ax=fig.add_axes([.50,.13,.48,.73],projection='3d',facecolor='#f5f7fa')
draw(ax,'housing');draw(ax,'door');draw(ax,'tray',z=28);draw(ax,'components',z=28);draw(ax,'module_cage',z=34);draw(ax,'ties',z=28);draw(ax,'tie_heads',z=28)
holder_wire(ax,28);draw(ax,'battery',z=28)
draw(ax,'lid',z=62);draw(ax,'magnets',z=62);draw(ax,'cover',z=75)
finish_mesh(ax)
style(ax,(-2,102),(-6,34),(-1,110),elev=23,azim=-61)
ax.text2D(.05,.89,'分解状態',transform=ax.transAxes,fontsize=14)
ax.text2D(.07,.05,'緑：取り外せるPLA部品トレー\n点線：電池ホルダーの収納範囲\nホルダーの開口を背面へ変更',transform=ax.transAxes,fontsize=11,color='#3e4b59')
fig.text(.05,.055,'背面のスライドふたから電池を交換。磁石カバーのねじを外さず、配線・ホルダーを動かしません。',fontsize=10,color='#6d7785')
fig.savefig(OUT/'bar-preview.png',dpi=150);plt.close(fig)

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
    style(ax,(6,95),(0,29),(0,25),elev=-45 if i==2 else 45,azim=-63)
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
    style(ax,(-55,104),(0,51),(-1,33),elev=27,azim=58)
    ax.text2D(.05,.93,title,transform=ax.transAxes,fontsize=14)
    ax.text2D(.05,.05,['ふたの爪で閉位置を保持\n追加のねじ・ナットは不要','ふたを取り外し、電池だけ交換\n点線：固定したホルダーの収納範囲'][i],transform=ax.transAxes,fontsize=11,color='#3e4b59')
fig.text(.04,.055,'本体の交換口：53 × 12.1 mm。レール・爪の公差と電池の着脱は、印刷品と手持ちホルダーで確認が必要です。',fontsize=11,color='#6d7785')
fig.savefig(OUT/'battery-access-preview.png',dpi=150);plt.close(fig)

fig=plt.figure(figsize=(12,6),facecolor='#f5f7fa')
fig.suptitle('kb-1 ケースとの取り付け確認',fontsize=19,x=.05,ha='left',y=.94)
ax=fig.add_axes([.07,.19,.87,.61],facecolor='#f5f7fa')
for name,color in [('keyboard','#b4bdc9'),('housing',COLORS['housing']),('lid',COLORS['lid']),('cover',COLORS['cover'])]:
    vs=np.asarray(MESH[name]['vertices'])
    tri=vs[np.asarray(MESH[name]['triangles'])]
    if name=='lid':
        roof=CHECK['contact_center_height_mm']-(tri[:,:,1]-14)*np.tan(np.deg2rad(CHECK['tenting_angle_deg']))-CHECK['total_lid_thickness_vertical_mm']
        tri=tri[np.all(tri[:,:,2]>=roof-1e-4,axis=1)]
    faces=tri[:,:,[1,2]]
    ax.add_collection(PolyCollection(faces,facecolors=color,edgecolors='none',antialiased=False))
ax.axhline(0,color='#43576b',linewidth=1.5)
ax.set_xlim(-25,130);ax.set_ylim(-2,38);ax.set_aspect('equal')
ax.set_xlabel('バーを横から見た位置 (mm)',fontsize=11)
ax.set_ylabel('高さ (mm)',fontsize=11)
ax.spines[['top','right']].set_visible(False)
ax.text(47,21,'kb-1 ケース',fontsize=12,color='#576475')
ax.text(6,9,'バー',fontsize=12,color='white')
ax.text(104,1.8,'机の面',fontsize=11,color='#43576b')
fig.text(.05,.065,'バーの長手方向から見たCAD投影。中央高さ%.0f mm、傾斜約%.1f°。灰色のケース底面が机に接します。'%(CHECK['contact_center_height_mm'],CHECK['tenting_angle_deg']),fontsize=11,color='#4c5968')
fig.savefig(OUT/'keyboard-fit-preview.png',dpi=150);plt.close(fig)
print('Saved bar, tray, battery-access and keyboard-fit previews')
