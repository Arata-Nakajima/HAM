#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/param.h>
#include <math.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "freertos/event_groups.h"
#include "freertos/ringbuf.h"

#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "protocol_examples_common.h"
//#include "addr_from_stdin.h"
#include "lwip/err.h"
#include "lwip/sockets.h"

#include "driver/gpio.h"

#include "sdkconfig.h"

#include "hal/gpio_ll.h"
#include "driver/gpio.h"
#include "driver/mcpwm.h"

#define READ_MODE_EN 1
#define DETECT_MOTION_EN 1
#define DRIVE_ACTUATERS_EN 1

#define RING_BUF_SIZE 240
#define GPIO_NUM_1 1
#define LEN_ASSIST 100
#define LEN_HOLD 50
#define ACT_NUM 6
#define UNIT_NUM 2
#define UNIT_ONE 0
#define UNIT_TWO 1
#define VDD 1
#define GND 0
#define ENCODER_PIN_A 32
#define ENCODER_PIN_B 33
#define DELTA_X_DIGIT 3
#define MINUS 1
#define PLUS 0
#define DUTY_MIN 50
#define DUTY_MAX 100
#define DUTY_STEP 1
#define WAIT_TIME_MS 1

//static const char *TAG = "ham_v1";
static const gpio_num_t GPIO_PH[UNIT_NUM] = { GPIO_NUM_16, GPIO_NUM_25 };
static const gpio_num_t GPIO_EN[UNIT_NUM] = { GPIO_NUM_17, GPIO_NUM_26 };
static const mcpwm_io_signals_t MCPWM_UNIT[UNIT_NUM] = { MCPWM_UNIT_0, MCPWM_UNIT_1 };
static const mcpwm_io_signals_t PWM_PORT_PH[UNIT_NUM] = { MCPWM0A, MCPWM1A };
static const mcpwm_io_signals_t PWM_PORT_EN[UNIT_NUM] = { MCPWM0B, MCPWM1B };
//static const mcpwm_timer_t TIMER[ACT_NUM] = { 0, 1 };

RingbufHandle_t mode_rbf; // Ring Buffer Handler for mode
RingbufHandle_t delta_x_rbf; // Ring Buffer Handler for delta_x

char mode[8] = "RIGID";
int counter[ACT_NUM] = {0};
      
static void periodic_timer_callback( void* arg ){}

static void read_mode( void *pvParameters ) {

  int cnt = 0;
  char prev_mode[8] = "RIGID";
  UBaseType_t res = pdTRUE;

  // 入力に設定するGPIO番号のビットマスク
  gpio_num_t input_pins[] = {GPIO_NUM_32, GPIO_NUM_33};
  // 出力に設定するGPIO番号のビットマスク
  gpio_num_t output_pins[] = {GPIO_NUM_34, GPIO_NUM_35};

  // 入力ピン設定
  gpio_config_t io_conf = {};
  io_conf.intr_type = GPIO_INTR_DISABLE;  // 割り込み無効
  io_conf.mode = GPIO_MODE_INPUT;
  io_conf.pin_bit_mask = ((1ULL << input_pins[0]) | (1ULL << input_pins[1]));
  io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
  io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
  gpio_config(&io_conf);

  // 出力ピン設定
  io_conf.mode = GPIO_MODE_OUTPUT;
  io_conf.pin_bit_mask = ((1ULL << output_pins[0]) | (1ULL << output_pins[1]));
  gpio_config(&io_conf);

  while ( 1 ) { 
    cnt = 0;
    strcpy(mode, prev_mode);

    vTaskDelay( 200 / portTICK_RATE_MS );
    if ( gpio_get_level( GPIO_NUM_1 ) == GND ) cnt ++;
    vTaskDelay( 200 / portTICK_RATE_MS );
    if ( gpio_get_level( GPIO_NUM_1 ) == GND ) cnt ++;

    if ( cnt == 1 ) {
      strcpy( mode, "ASSIST" );
    } else {
      strcpy( mode, "HOLD" );
    }
    strcpy(prev_mode, mode);
    res = xRingbufferSend( mode_rbf, mode, sizeof( mode ), pdMS_TO_TICKS( 10000 ) );
    //printf( "read_mode send mode %d\n", sizeof(mode));

    //printf( "%6lld ms C\n", esp_timer_get_time() / 1000 );

    if ( res != pdTRUE ) {
      printf( "Failed to send item\n" );
    }  
  }
}

static void read_rigid_mode( void *pvParameters ) {

  int cnt = 0;

  while ( 1 ) {

    cnt = 0;
    if ( gpio_get_level( GPIO_NUM_1 ) == GND ) cnt ++;
    vTaskDelay( 1000 / portTICK_RATE_MS );
    if ( gpio_get_level( GPIO_NUM_1 ) == GND ) cnt ++;

    if ( cnt == 2 ) {
      strcpy( mode, "RIGID" );
    }
  }  
}

void detect_single_motion( int act_num ) {

  //volatile int aState;
  //volatile int bState;
  //volatile int aLastState;
  int aState = 0;
  int bState = 0;
  int aLastState = 0;
    
  aState = gpio_get_level( ENCODER_PIN_A );
  bState = gpio_get_level( ENCODER_PIN_B );
  //printf( "States %d, %d, %d\n", aState, bState, aLastState );

  if ( aState != aLastState ) {
    if ( bState != aState ) {
      counter[act_num]++;
    } else {
      counter[act_num]--;
    }
  }
  printf( "States %d, %d, %d\n", aState, bState, aLastState );
  aLastState = aState;
}

static void detect_motions( void *pvParameters ) {

  UBaseType_t res = pdTRUE;
  //char cnt_str[DELTA_X_DIGIT];
  char msg[ACT_NUM * DELTA_X_DIGIT] = { '\0' };

  while (1) {
    for ( int act_num = 0; act_num < ACT_NUM; act_num ++ ) {
      detect_single_motion( act_num );
      //printf( "Count %4d, %4d\n", counter[act_num], act_num );
      //itoa( counter[act_num], cnt_str, 10 );
      //printf( "cnt_srt %s\n", cnt_str );
      vTaskDelay( 1000 / portTICK_RATE_MS );
      //sprintf( msg + strlen(msg), "%4s", cnt_str );
      //sprintf( msg + act_num * (DELTA_X_DIGIT + 1), "%2s", cnt_str );
      //sprintf( msg + act_num * (DELTA_X_DIGIT + 1), "%3d", counter[act_num] );
      sprintf( msg + strlen(msg) % 18, "%3d", counter[act_num] ); 
      //printf( "act_num %d, msg (%s), length (%d), counter %d\n", act_num, msg, strlen(msg) % 18, counter[act_num] );
    }
    
    //printf( "msg (%s), size (%d)\n", msg, sizeof(msg) );
    res =  xRingbufferSend( delta_x_rbf, msg, sizeof( msg ), pdMS_TO_TICKS( 10000 ) );
    //printf( "detect_motions send msg %d\n", sizeof(msg));
    //printf( "%6lld ms C\n", esp_timer_get_time() / 1000 );

    if ( res != pdTRUE ) {
      printf( "Failed to send item, delta_x\n" );
    }
  }
}

char **splitDigits( char *str ) {
  char **counts = malloc( ACT_NUM * DELTA_X_DIGIT * sizeof(char *) );

  for ( int act_num = 0; act_num < ACT_NUM; act_num++ ) {
    counts[act_num] = strndup( str + act_num * DELTA_X_DIGIT, DELTA_X_DIGIT );
    //printf( "counts %s\n", counts[act_num]);
  }
  return counts;
}

int slideLength( char* mode ) {
  if ( strcmp( mode, "ASSIST" ) == 0 ) return LEN_ASSIST;
  else if ( strcmp( mode, "HOLD" ) == 0 ) return LEN_HOLD;
  else return -1;
}

void drive_single_actuator( int act_num, int length, int unit_num ) {

  printf( "act_num %d, PWM_PORT_PH %d, GPIO_PH %d\n", act_num, PWM_PORT_PH[unit_num], GPIO_PH[unit_num] );
  mcpwm_gpio_init( MCPWM_UNIT[unit_num], PWM_PORT_PH[unit_num], GPIO_PH[unit_num] );
  printf( "act_num %d, PWM_PORT_EN %d, GPIO_EN %d\n", act_num, PWM_PORT_EN[unit_num], GPIO_EN[unit_num] );
  mcpwm_gpio_init( MCPWM_UNIT[unit_num], PWM_PORT_EN[unit_num], GPIO_EN[unit_num] );

  mcpwm_config_t pwm_config;
  pwm_config.frequency = 10*1000; // PWM周波数= 10kHz,
  pwm_config.cmpr_a = 0; // デューティサイクルの初期値（0%）
  pwm_config.cmpr_b = 50; // デューティサイクルの初期値（0%）
  pwm_config.counter_mode = MCPWM_UP_COUNTER;
  pwm_config.duty_mode = MCPWM_DUTY_MODE_0; // アクティブハイ

  mcpwm_init( MCPWM_UNIT[unit_num], MCPWM_TIMER_0, &pwm_config );

  bool reach_T = gpio_get_level( GPIO_NUM_2 ) & 1;
  bool reach_B = gpio_get_level( GPIO_NUM_3 ) & 1;
  int limitSwitch = (int)( ( reach_T << 1 ) | reach_B );
  bool limit_T = ( signbit( (float) length  ) == MINUS ) & ( limitSwitch == 2 ); 
  bool limit_B = ( signbit( (float) length  ) == PLUS ) & ( limitSwitch == 1 );

  // limit unreached || uppper limit && go downwords || lower limit && go upwards
  if ( ( limitSwitch == 0 ) | limit_T | limit_B ) {
    if ( signbit( (float) length ) == PLUS ) {
      mcpwm_set_signal_high( MCPWM_UNIT[unit_num], MCPWM_TIMER_0, MCPWM_OPR_A );
    } else {
      mcpwm_set_signal_low( MCPWM_UNIT[unit_num], MCPWM_TIMER_0, MCPWM_OPR_A );
    }

    for ( int duty = DUTY_MIN; duty < DUTY_MAX; duty += DUTY_STEP ) {
      mcpwm_set_duty( MCPWM_UNIT[unit_num], MCPWM_TIMER_0, MCPWM_OPR_B, duty );
      vTaskDelay(WAIT_TIME_MS / portTICK_RATE_MS);
    }
    // Always need set_duty_type after set_signal_low/high
    mcpwm_set_duty_type( MCPWM_UNIT[unit_num], MCPWM_TIMER_0, MCPWM_OPR_B, MCPWM_DUTY_MODE_0 );

  } else {
    // Stop Actuater
    mcpwm_set_signal_low( MCPWM_UNIT[unit_num], MCPWM_TIMER_0, MCPWM_OPR_B );
  }
}

static void drive_actuaters( void *pvParameters ) {
  size_t mode_len;
  size_t delta_X_len;
  int sign = 0;
  int delta_x[ ACT_NUM ] = {0};
  //char dummy_msg[ACT_NUM * DELTA_X_DIGIT] = { '\0' };
  char **counts;

  while (1) {

    char *mode = ( char * ) xRingbufferReceive( mode_rbf, &mode_len, pdMS_TO_TICKS( 1000 ) );
    //printf( "drive_act receive mode %s\n", mode);
    
    vTaskDelay( 1 / portTICK_RATE_MS );
    
    if ( mode != NULL ) {
      vRingbufferReturnItem( mode_rbf, (void *) mode );
    } else {
      printf( "Failed to receive item, mode\n" );
    }

    char *t_delta_X = ( char * ) xRingbufferReceive( delta_x_rbf, &delta_X_len, pdMS_TO_TICKS( 1000 ) );

    vTaskDelay( 1 / portTICK_RATE_MS );
    
    if ( t_delta_X != NULL ) {
      printf( "msg %s\n", t_delta_X );
      vRingbufferReturnItem( delta_x_rbf, (void *) t_delta_X );
#if 1
      counts = splitDigits( t_delta_X );
      for ( int act_num = 0; act_num < ACT_NUM; act_num ++ ) {
        delta_x[ act_num ] = atoi( counts[ act_num ] );
        //printf( "delta_x %d\n", delta_x[act_num]);
        if ( delta_x[ act_num ] != 0 ) {
          sign = ( signbit( (float) delta_x[ act_num ] ) ? -1 : 1 );
          drive_single_actuator( act_num, sign * slideLength( mode ), UNIT_ONE );
          //drive_single_actuator( act_num, sign * slideLength( mode ), UNIT_TWO );
        }
      }
#endif
    } else {
      //printf( "Failed to receive item, delta_x\n" );
      //memcpy( t_delta_X, dummy_msg, sizeof(dummy_msg));
    }
    //vTaskDelete( NULL );
    //free( counts );
  }
}

void app_main(void) {

#if 0
  ESP_ERROR_CHECK( nvs_flash_init() );
  ESP_ERROR_CHECK( esp_netif_init() );
  ESP_ERROR_CHECK( esp_event_loop_create_default() );
  ESP_ERROR_CHECK( example_connect() );

  esp_timer_handle_t ham_timer;

  const esp_timer_create_args_t timer_args = {
    .callback = &periodic_timer_callback,
    /* name is optional, but may help identify the timer when debugging */
    .name = "ham time stamp"
  };

  ESP_ERROR_CHECK( esp_timer_create( &timer_args, &ham_timer ));
  ESP_ERROR_CHECK( esp_timer_start_periodic( ham_timer, 0 ));
#endif

#if READ_MODE_EN
  mode_rbf = xRingbufferCreate( RING_BUF_SIZE, RINGBUF_TYPE_NOSPLIT );
  if ( mode_rbf == NULL ) {
    printf( "Failed to create ring buffer, mode\n" );
  }

  xTaskCreate( read_mode, "read_mode", 4096, NULL, 4, NULL );
  xTaskCreate( read_rigid_mode, "read_rigid_mode", 4096, NULL, 4, NULL );
#endif

#if DETECT_MOTION_EN
  delta_x_rbf = xRingbufferCreate( RING_BUF_SIZE, RINGBUF_TYPE_NOSPLIT );
  if ( delta_x_rbf == NULL ) {
    printf( "Failed to create ring buffer, delta_x\n" );
  }

  xTaskCreate( detect_motions, "detect_motion", 4096, NULL, 5, NULL );
#endif

#if DRIVE_ACTUATERS_EN
  xTaskCreate( drive_actuaters, "drive_actuaters", 4096, NULL, 6, NULL );
#endif
}
