from flask import Flask, render_template, Response, jsonify, request
import cv2
import yaml
import time
import logging
from .state import state

def create_app():
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/config')
    def config_page():
        # Load the latest config from file to ensure we have current state
        try:
            with open(state.config_path, 'r') as f:
                config_content = f.read()
        except Exception as e:
            config_content = f"# Error loading config: {e}"
            
        return render_template('config.html', config_content=config_content)
        
    @app.route('/api/config', methods=['POST'])
    def save_config():
        new_config_str = request.json.get('config')
        if not new_config_str:
            return jsonify({"success": False, "error": "No config provided"}), 400
            
        try:
            # Validate YAML
            new_config = yaml.safe_load(new_config_str)
            
            # Save to file
            with open(state.config_path, 'w') as f:
                f.write(new_config_str)
            
            # Update shared state
            state.config = new_config
            
            return jsonify({"success": True})
        except yaml.YAMLError as e:
            return jsonify({"success": False, "error": f"Invalid YAML: {e}"}), 400
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    def generate_frames():
        while True:
            frame = state.get_frame()
            if frame is None:
                # If no frame is available, yield a placeholder or wait
                time.sleep(0.1)
                continue
                
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
                
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # Limit streaming framerate to save resources
            time.sleep(0.033) # ~30 FPS

    @app.route('/video_feed')
    def video_feed():
        return Response(generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
                        
    @app.route('/api/stats')
    def get_stats():
        if state.database is None:
            return jsonify({"error": "Database not initialized"})
            
        try:
            # Get stats from database
            total_count = state.database.get_vehicle_count()
            
            # Get today's counts by direction (needs DB support, or we calculate from raw)
            # For now, let's just get total count
            
            # Calculate uptime
            uptime = time.time() - state.system_stats.get('start_time', time.time())
            
            return jsonify({
                "total_vehicles": total_count,
                "fps": state.system_stats.get('fps', 0),
                "uptime_seconds": int(uptime),
                "cloud_enabled": state.database.cloud_enabled
            })
        except Exception as e:
            logging.error(f"Error getting stats: {e}")
            return jsonify({"error": str(e)})

    return app

