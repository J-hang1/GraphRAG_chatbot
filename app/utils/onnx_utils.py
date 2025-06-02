"""
ONNX Utilities - Helper functions for ONNX model debugging
"""

from typing import Dict, List, Any
from ..utils.logger import log_info, log_error

def debug_onnx_model(model_session, model_name: str = "Unknown") -> Dict[str, Any]:
    """
    Debug ONNX model inputs và outputs
    
    Args:
        model_session: ONNX Runtime InferenceSession
        model_name: Tên model để log
        
    Returns:
        Dict chứa thông tin về inputs và outputs
    """
    try:
        # Get input info
        inputs_info = []
        for input_meta in model_session.get_inputs():
            input_info = {
                'name': input_meta.name,
                'type': str(input_meta.type),
                'shape': input_meta.shape
            }
            inputs_info.append(input_info)
            log_info(f"📥 {model_name} Input: {input_info}")
        
        # Get output info
        outputs_info = []
        for output_meta in model_session.get_outputs():
            output_info = {
                'name': output_meta.name,
                'type': str(output_meta.type),
                'shape': output_meta.shape
            }
            outputs_info.append(output_info)
            log_info(f"📤 {model_name} Output: {output_info}")
        
        return {
            'inputs': inputs_info,
            'outputs': outputs_info,
            'input_names': [inp['name'] for inp in inputs_info],
            'output_names': [out['name'] for out in outputs_info]
        }
        
    except Exception as e:
        log_error(f"❌ Lỗi debug ONNX model {model_name}: {str(e)}")
        return {
            'inputs': [],
            'outputs': [],
            'input_names': [],
            'output_names': [],
            'error': str(e)
        }

def get_model_input_name(model_session, fallback_name: str = "input") -> str:
    """
    Lấy tên input đầu tiên của ONNX model
    
    Args:
        model_session: ONNX Runtime InferenceSession
        fallback_name: Tên fallback nếu không lấy được
        
    Returns:
        Tên input của model
    """
    try:
        if model_session and len(model_session.get_inputs()) > 0:
            input_name = model_session.get_inputs()[0].name
            log_info(f"🎯 Model input name: {input_name}")
            return input_name
        else:
            log_error(f"❌ Không thể lấy input name, sử dụng fallback: {fallback_name}")
            return fallback_name
    except Exception as e:
        log_error(f"❌ Lỗi get_model_input_name: {str(e)}, sử dụng fallback: {fallback_name}")
        return fallback_name

def run_model_with_auto_input(model_session, input_data, model_name: str = "Unknown"):
    """
    Chạy ONNX model với tự động detect input name
    
    Args:
        model_session: ONNX Runtime InferenceSession
        input_data: Input data (numpy array)
        model_name: Tên model để log
        
    Returns:
        Model outputs
    """
    try:
        # Lấy tên input đầu tiên
        input_name = get_model_input_name(model_session)
        
        # Chạy model
        outputs = model_session.run(None, {input_name: input_data})
        
        return outputs
        
    except Exception as e:
        log_error(f"❌ Lỗi run_model_with_auto_input cho {model_name}: {str(e)}")
        raise e
