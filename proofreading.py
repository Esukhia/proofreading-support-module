import copy
from pathlib import Path
from openpecha.blupdate import *
from openpecha.cli import download_pecha
from openpecha.utils import load_yaml, dump_yaml

def get_meta(pecha_id, pecha_path=None):
    if not pecha_path:
        pecha_path = download_pecha(pecha_id)
    meta = load_yaml(Path(f"{pecha_path}/{pecha_id}.opf/meta.yml"))
    return meta

def get_pagination_layer(pecha_id, vol_num, pecha_path=None):
    vol_id = f'v{int(vol_num):03}'
    if not pecha_path:
        pecha_path = download_pecha(pecha_id)
    pagination_layer = load_yaml(Path(f'{pecha_path}/{pecha_id}.opf/layers/{vol_id}/Pagination.yml'))
    return pagination_layer

def get_vol_info(pecha_id, vol_num, pecha_path=None):
    pages = []
    pagination_layer = get_pagination_layer(pecha_id, vol_num, pecha_path)
    pages = [ann_uuid for ann_uuid, ann in pagination_layer['annotations'].items()]
    return pages

def get_base_text(pecha_id, vol_num, pecha_path=None):
    base_text = ''
    vol_id = f'v{int(vol_num):03}'
    if not pecha_path:
        pecha_path = download_pecha(pecha_id)
    base_text = Path(f'{pecha_path}/{pecha_id}.opf/base/{vol_id}.txt').read_text(encoding='utf-8')
    return base_text

def get_page_content(page_ann, base_text):
    page_span = page_ann['span']
    page_start_idx = page_span['start']
    page_end_idx = page_span['end']
    page_content = base_text[page_start_idx:page_end_idx+1]
    return page_content

def get_page_image_url(meta_data, page_ann, vol_num):
    cur_image_grp_id = ''
    for vol_id, vol_info in meta_data['source_metadata']['volumes'].items():
        if vol_info['volume_number'] == vol_num:
            cur_image_grp_id = vol_info['image_group_id']
    image_ref = page_ann['reference']
    image_url = f"https://iiif.bdrc.io/bdr:{cur_image_grp_id}::{image_ref}/full/max/0/default.jpg"
    return image_url

def get_page(pecha_id, vol_num, page_id, pecha_path=None):
    page_info = {
        'content': None,
        'image_url': None,
    }
    pagination_layer = get_pagination_layer(pecha_id, vol_num, pecha_path)
    base_text = get_base_text(pecha_id, vol_num, pecha_path)
    cur_page_ann = pagination_layer['annotations'][page_id]
    meta_data = get_meta(pecha_id, pecha_path)
    page_info['content'] = get_page_content(cur_page_ann, base_text)
    page_info['image_url'] = get_page_image_url(meta_data, cur_page_ann, vol_num)
    return page_info

    
def get_new_vol(old_vol, old_page, new_page_content):
    old_page = old_page.strip()
    new_page = new_page_content.strip()
    new_vol = old_vol.replace(old_page, new_page)
    return new_vol

def update_layer(pecha_path, pecha_id, vol_id, old_layers, updater):
    for layer_name, old_layer in old_layers.items():
        update_ann_layer(old_layer, updater)
        new_layer_path = (pecha_path / f"{pecha_id}.opf/layers/{vol_id}/{layer_name}.yml")
        dump_yaml(old_layer, new_layer_path)
        print(f'INFO: {vol_id} {layer_name} has been updated...')

def get_old_layers(pecha_path, pecha_id, vol_id):
    old_layers = {}
    layer_paths = list((pecha_path / f"{pecha_id}.opf/layers/{vol_id}").iterdir())
    for layer_path in layer_paths:
        layer_name = layer_path.stem
        layer_content = load_yaml(layer_path)
        old_layers[layer_name] = layer_content
    return old_layers
       
def update_old_layers(pecha_path, pecha_id, old_vol, new_vol, vol_id):
    updater = Blupdate(old_vol, new_vol)
    old_layers = get_old_layers(pecha_path, pecha_id, vol_id)
    update_layer(pecha_path, pecha_id, vol_id, old_layers, updater)

def update_base(pecha_path, pecha_id, vol_num, new_vol):
    Path(f"{pecha_path}/{pecha_id}.opf/base/v{int(vol_num):03}.txt").write_text(new_vol, encoding='utf-8')
    print(f'INFO: {vol_num} base updated..')

def update_index(vol_offset, vol_num, page_start, old_pecha_idx):
    if vol_offset != 0:
        for text_uuid, text_ann in old_pecha_idx["annotations"].items():
            text_span = text_ann['span']
            for vol_walker, vol_span in enumerate(text_span):
                if vol_span['vol'] == vol_num and vol_span['end'] >= page_start:
                    old_pecha_idx["annotations"][text_uuid]['span'][vol_walker]['end'] += vol_offset
                elif vol_span['vol'] > vol_num:
                    break
    return old_pecha_idx

def save_page(pecha_id, vol_num, page_id, page_content, pecha_path=None):
    vol_id = f'v{int(vol_num):03}'
    if not pecha_path:
        pecha_path = download_pecha(pecha_id)
    old_pecha_idx = load_yaml(Path(f'{pecha_path}/{pecha_id}.opf/index.yml'))
    pagination_layer = get_pagination_layer(pecha_id, vol_num, pecha_path)
    old_vol = get_base_text(pecha_id, vol_num, pecha_path)
    cur_page_ann = pagination_layer['annotations'][page_id]
    old_page = get_page_content(cur_page_ann, old_vol)
    new_vol = get_new_vol(old_vol, old_page, new_page_content=page_content)
    vol_offset = len(new_vol) - len(old_vol)
    new_pecha_idx = update_index(vol_offset, vol_num, cur_page_ann['span']['start'], old_pecha_idx)
    update_old_layers(pecha_path, pecha_id, old_vol, new_vol, vol_id)
    update_base(pecha_path, pecha_id, vol_num, new_vol)
    new_pecha_idx_path = dump_yaml(new_pecha_idx, (pecha_path / f'{pecha_id}.opf/index.yml'))
    return pecha_path
    

