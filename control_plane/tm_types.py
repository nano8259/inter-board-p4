from enum import Enum

class AppPool(Enum):
    BF_TM_IG_APP_POOL_0 = 0  # Ingress Application Pool 0 
    BF_TM_IG_APP_POOL_1 = 1  # Ingress Application Pool 1 
    BF_TM_IG_APP_POOL_2 = 2  # Ingress Application Pool 2 
    BF_TM_IG_APP_POOL_3 = 3  # Ingress Application Pool 3 
    BF_TM_EG_APP_POOL_0 = 4  # Egress Application Pool 0 
    BF_TM_EG_APP_POOL_1 = 5  # Egress Application Pool 1 
    BF_TM_EG_APP_POOL_2 = 6  # Egress Application Pool 2 
    BF_TM_EG_APP_POOL_3 = 7  # Egress Application Pool 3 
    BF_TM_APP_POOL_LAST = 8

class QueueBaf(Enum):
    BF_TM_Q_BAF_1_POINT_5_PERCENT = 0  # 1.5%  
    BF_TM_Q_BAF_3_PERCENT = 1  # 3%    
    BF_TM_Q_BAF_6_PERCENT = 2  # 6%    
    BF_TM_Q_BAF_11_PERCENT = 3  # 11%   
    BF_TM_Q_BAF_20_PERCENT = 4  # 20%   
    BF_TM_Q_BAF_33_PERCENT = 5  # 33%   
    BF_TM_Q_BAF_50_PERCENT = 6  # 50%   
    BF_TM_Q_BAF_66_PERCENT = 7  # 66%   
    BF_TM_Q_BAF_80_PERCENT = 8  # 80%   
    BF_TM_Q_BAF_DISABLE = 9  # If BAF is disabled, queue threshold is static. 
    
class QueueColorLimit(Enum):
    BF_TM_Q_COLOR_LIMIT_12_POINT_5_PERCENT = 0  # 12.5% of green color limits 
    BF_TM_Q_COLOR_LIMIT_25_PERCENT = 1  # 25% of green color limits   
    BF_TM_Q_COLOR_LIMIT_37_POINT_5_PERCENT = 2  # 37.5% of green color limits 
    BF_TM_Q_COLOR_LIMIT_50_PERCENT = 3  # 50% of green color limits   
    BF_TM_Q_COLOR_LIMIT_62_POINT_5_PERCENT = 4  # 62.5% of green color limits 
    BF_TM_Q_COLOR_LIMIT_75_PERCENT = 5  # 75% of green color limits   
    BF_TM_Q_COLOR_LIMIT_87_POINT_5_PERCENT = 6  # 87% of green color limits   
    BF_TM_Q_COLOR_LIMIT_100_PERCENT = 7  # 100% of green color limits  
    
class QueueColor(Enum):
    BF_TM_COLOR_GREEN = 0  # Enum to use for Green Color 
    BF_TM_COLOR_YELLOW = 1  # Enum to use for Yellow Color 
    BF_TM_COLOR_RED = 2  # Enum to use for Red Color 
    
class SchedPrio(Enum):
    BF_TM_SCH_PRIO_LOW = 0  # ,
    BF_TM_SCH_PRIO_0 = BF_TM_SCH_PRIO_LOW  # Scheduling Priority (Low) = BF_TM_SCH_PRIO_LOW,
    BF_TM_SCH_PRIO_1 = 1  #  One of eight scheduling priority,
    BF_TM_SCH_PRIO_2 = 2  #  One of eight scheduling priority,
    BF_TM_SCH_PRIO_3 = 3  #  One of eight scheduling priority,
    BF_TM_SCH_PRIO_4 = 4  #  One of eight scheduling priority,
    BF_TM_SCH_PRIO_5 = 5  #  One of eight scheduling priority,
    BF_TM_SCH_PRIO_6 = 6  #  One of eight scheduling priority,
    BF_TM_SCH_PRIO_7 = 7  #  Scheduling Priority (High),
    BF_TM_SCH_PRIO_HIGH = BF_TM_SCH_PRIO_7