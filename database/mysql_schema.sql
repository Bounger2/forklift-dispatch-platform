CREATE DATABASE IF NOT EXISTS forklift_dispatch
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE forklift_dispatch;

CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  name VARCHAR(64) NOT NULL,
  phone VARCHAR(32) DEFAULT '',
  wecom_user_id VARCHAR(128) DEFAULT '',
  department VARCHAR(128) DEFAULT '',
  team VARCHAR(64) DEFAULT '',
  role VARCHAR(32) NOT NULL,
  status VARCHAR(32) DEFAULT 'active',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_users_username (username),
  INDEX idx_users_wecom (wecom_user_id),
  INDEX idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE drivers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  employee_no VARCHAR(64) NOT NULL UNIQUE,
  license_level VARCHAR(64) DEFAULT 'N2',
  qualification_tags VARCHAR(255) DEFAULT 'standard',
  shift_status VARCHAR(32) DEFAULT 'off_shift',
  bind_status VARCHAR(32) DEFAULT 'unbound',
  workload_score DOUBLE DEFAULT 0,
  task_count_today INT DEFAULT 0,
  working_minutes_today INT DEFAULT 0,
  distance_today DOUBLE DEFAULT 0,
  emergency_count_today INT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_drivers_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE forklifts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  plate_no VARCHAR(64) DEFAULT '',
  model VARCHAR(64) DEFAULT '',
  power_type VARCHAR(32) DEFAULT 'electric',
  tonnage DOUBLE DEFAULT 3,
  status VARCHAR(32) DEFAULT 'idle',
  battery_level INT DEFAULT 90,
  fuel_level INT DEFAULT 0,
  online BOOLEAN DEFAULT TRUE,
  current_area VARCHAR(128) DEFAULT '',
  current_x DOUBLE DEFAULT 50,
  current_y DOUBLE DEFAULT 50,
  heading DOUBLE DEFAULT 0,
  speed DOUBLE DEFAULT 0,
  last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  driver_id INT NULL,
  note VARCHAR(255) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_forklifts_code (code),
  INDEX idx_forklifts_status (status),
  CONSTRAINT fk_forklifts_driver FOREIGN KEY (driver_id) REFERENCES drivers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE map_points (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  point_type VARCHAR(32) DEFAULT 'pickup',
  area VARCHAR(128) DEFAULT '',
  x DOUBLE NOT NULL,
  y DOUBLE NOT NULL,
  lat DOUBLE NULL,
  lng DOUBLE NULL,
  geofence_radius DOUBLE DEFAULT 5,
  contact VARCHAR(128) DEFAULT '',
  enabled BOOLEAN DEFAULT TRUE,
  is_temporary BOOLEAN DEFAULT FALSE,
  description VARCHAR(255) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_map_points_name (name),
  INDEX idx_map_points_type (point_type),
  INDEX idx_map_points_temporary (is_temporary)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE gps_calibration_points (
  id INT AUTO_INCREMENT PRIMARY KEY,
  corner_key VARCHAR(16) NOT NULL UNIQUE,
  label VARCHAR(64) NOT NULL,
  x DOUBLE NOT NULL,
  y DOUBLE NOT NULL,
  lat DOUBLE NULL,
  lng DOUBLE NULL,
  enabled BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_gps_calibration_corner (corner_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE transport_tasks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  task_no VARCHAR(64) NOT NULL UNIQUE,
  requester_id INT NULL,
  origin_point_id INT NULL,
  dest_point_id INT NULL,
  origin_label VARCHAR(128) NOT NULL,
  dest_label VARCHAR(128) NOT NULL,
  cargo_type VARCHAR(128) DEFAULT '',
  estimated_weight DOUBLE DEFAULT 0,
  pallet_count INT DEFAULT 1,
  expected_finish_at DATETIME NULL,
  priority VARCHAR(8) DEFAULT 'B',
  status VARCHAR(32) DEFAULT 'pending_review',
  assigned_forklift_id INT NULL,
  assigned_driver_id INT NULL,
  eta_minutes INT DEFAULT 0,
  distance DOUBLE DEFAULT 0,
  note TEXT,
  abnormal_reason VARCHAR(255) DEFAULT '',
  assigned_at DATETIME NULL,
  accepted_at DATETIME NULL,
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_tasks_task_no (task_no),
  INDEX idx_tasks_status (status),
  INDEX idx_tasks_priority (priority),
  CONSTRAINT fk_tasks_requester FOREIGN KEY (requester_id) REFERENCES users(id),
  CONSTRAINT fk_tasks_origin FOREIGN KEY (origin_point_id) REFERENCES map_points(id),
  CONSTRAINT fk_tasks_dest FOREIGN KEY (dest_point_id) REFERENCES map_points(id),
  CONSTRAINT fk_tasks_forklift FOREIGN KEY (assigned_forklift_id) REFERENCES forklifts(id),
  CONSTRAINT fk_tasks_driver FOREIGN KEY (assigned_driver_id) REFERENCES drivers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE task_events (
  id INT AUTO_INCREMENT PRIMARY KEY,
  task_id INT NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  operator_id INT NULL,
  forklift_id INT NULL,
  driver_id INT NULL,
  location_x DOUBLE NULL,
  location_y DOUBLE NULL,
  message VARCHAR(255) DEFAULT '',
  payload JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_task_events_task (task_id),
  CONSTRAINT fk_events_task FOREIGN KEY (task_id) REFERENCES transport_tasks(id),
  CONSTRAINT fk_events_operator FOREIGN KEY (operator_id) REFERENCES users(id),
  CONSTRAINT fk_events_forklift FOREIGN KEY (forklift_id) REFERENCES forklifts(id),
  CONSTRAINT fk_events_driver FOREIGN KEY (driver_id) REFERENCES drivers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE forklift_positions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  forklift_id INT NOT NULL,
  task_id INT NULL,
  recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  x DOUBLE NOT NULL,
  y DOUBLE NOT NULL,
  lat DOUBLE DEFAULT 0,
  lng DOUBLE DEFAULT 0,
  heading DOUBLE DEFAULT 0,
  speed DOUBLE DEFAULT 0,
  source VARCHAR(32) DEFAULT 'simulator',
  quality DOUBLE DEFAULT 0.95,
  area VARCHAR(128) DEFAULT '',
  INDEX idx_positions_forklift (forklift_id),
  INDEX idx_positions_time (recorded_at),
  CONSTRAINT fk_positions_forklift FOREIGN KEY (forklift_id) REFERENCES forklifts(id),
  CONSTRAINT fk_positions_task FOREIGN KEY (task_id) REFERENCES transport_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE shift_templates (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(64) NOT NULL,
  start_time VARCHAR(8) NOT NULL,
  end_time VARCHAR(8) NOT NULL,
  rest_minutes INT DEFAULT 60,
  area VARCHAR(128) DEFAULT '全厂',
  enabled BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE schedule_assignments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  shift_date DATE NOT NULL,
  shift_code VARCHAR(64) NOT NULL,
  driver_id INT NOT NULL,
  forklift_id INT NULL,
  area VARCHAR(128) DEFAULT '',
  status VARCHAR(32) DEFAULT 'scheduled',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_schedule_date (shift_date),
  CONSTRAINT fk_schedule_driver FOREIGN KEY (driver_id) REFERENCES drivers(id),
  CONSTRAINT fk_schedule_forklift FOREIGN KEY (forklift_id) REFERENCES forklifts(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE vehicle_bindings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  forklift_id INT NOT NULL,
  driver_id INT NOT NULL,
  shift_code VARCHAR(64) DEFAULT '',
  bound_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  unbound_at DATETIME NULL,
  status VARCHAR(32) DEFAULT 'active',
  bind_method VARCHAR(32) DEFAULT 'rfid',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_bindings_forklift FOREIGN KEY (forklift_id) REFERENCES forklifts(id),
  CONSTRAINT fk_bindings_driver FOREIGN KEY (driver_id) REFERENCES drivers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE dispatch_rules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(96) NOT NULL UNIQUE,
  name VARCHAR(128) NOT NULL,
  category VARCHAR(64) NOT NULL,
  rule_type VARCHAR(64) NOT NULL,
  priority INT DEFAULT 100,
  weight DOUBLE DEFAULT 0,
  enabled BOOLEAN DEFAULT TRUE,
  editable BOOLEAN DEFAULT TRUE,
  condition_json JSON,
  action_json JSON,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_rules_code (code),
  INDEX idx_rules_category (category),
  INDEX idx_rules_type (rule_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(96) NOT NULL UNIQUE,
  alert_type VARCHAR(64) NOT NULL,
  severity VARCHAR(16) DEFAULT 'info',
  status VARCHAR(32) DEFAULT 'open',
  title VARCHAR(128) NOT NULL,
  message TEXT,
  suggestion TEXT,
  task_id INT NULL,
  forklift_id INT NULL,
  driver_id INT NULL,
  map_point_id INT NULL,
  closed_at DATETIME NULL,
  closed_by_id INT NULL,
  payload JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_alerts_code (code),
  INDEX idx_alerts_type (alert_type),
  INDEX idx_alerts_status (status),
  INDEX idx_alerts_severity (severity),
  CONSTRAINT fk_alert_task FOREIGN KEY (task_id) REFERENCES transport_tasks(id),
  CONSTRAINT fk_alert_forklift FOREIGN KEY (forklift_id) REFERENCES forklifts(id),
  CONSTRAINT fk_alert_driver FOREIGN KEY (driver_id) REFERENCES drivers(id),
  CONSTRAINT fk_alert_point FOREIGN KEY (map_point_id) REFERENCES map_points(id),
  CONSTRAINT fk_alert_closed_by FOREIGN KEY (closed_by_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE wecom_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  target_user_id VARCHAR(128) DEFAULT '',
  target_role VARCHAR(64) DEFAULT '',
  title VARCHAR(128) NOT NULL,
  content TEXT,
  msg_type VARCHAR(32) DEFAULT 'text',
  status VARCHAR(32) DEFAULT 'pending',
  error TEXT,
  payload JSON,
  sent_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
