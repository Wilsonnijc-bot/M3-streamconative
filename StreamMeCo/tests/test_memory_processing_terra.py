import sys
import pytest
from mmagent.memory_processing_terra import build_request


def test_frames_are_chronological_and_voice_ids_preserved():
    frames=['frame_'+str(i) for i in range(10)]
    voices={7:[dict(start_time='00:00',end_time='00:01',asr='hello')]}
    payload=build_request(frames,{},voices,5,2)
    content=payload['input'][0]['content']
    images=[x['image_url'].split(',')[1] for x in content if x['type']=='input_image']
    assert images==['frame_0','frame_3','frame_5','frame_8']
    assert '<voice_7>' in content[-1]['text']
    assert payload['model']=='gpt-5.6-terra' and payload['reasoning']['effort']=='medium'
    assert payload['text']['format']['type']=='json_object'
    assert 'mmagent.utils.chat_qwen' not in sys.modules


def test_invalid_frame_rate_rejected():
    with pytest.raises(ValueError):build_request([],{}, {},0,2)
    with pytest.raises(ValueError):build_request([],{}, {},1,2)
