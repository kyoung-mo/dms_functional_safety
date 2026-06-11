/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * File Name          : freertos.c
  * Description        : Code for freertos applications
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "can.h"
#include "usart.h"
#include "gpio.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN Variables */
// 콜백으로 UART 수신
uint8_t rx_byte = 0;
uint8_t rx_buf[4];
uint8_t rx_idx = 0;
uint8_t rx_state = 0;

// 공유 상태에서 driver_state / ear : UART 콜백이 쓰고, CAN_Tx가 읽음.
volatile uint8_t driver_state = 0;
volatile uint8_t curr_ear = 0;
volatile uint8_t curr_seq = 0;
volatile uint8_t rpi_alive = 1;

// Watchdog 내부
static uint8_t last_seq = 0;
static uint8_t hb_fail_count = 0;
static uint8_t dtc_sent = 0;
/* USER CODE END Variables */
/* Definitions for Task_Watchdog */
osThreadId_t Task_WatchdogHandle;
const osThreadAttr_t Task_Watchdog_attributes = {
  .name = "Task_Watchdog",
  .stack_size = 256 * 4,
  .priority = (osPriority_t) osPriorityRealtime,
};
/* Definitions for Task_CAN_Tx */
osThreadId_t Task_CAN_TxHandle;
const osThreadAttr_t Task_CAN_Tx_attributes = {
  .name = "Task_CAN_Tx",
  .stack_size = 256 * 4,
  .priority = (osPriority_t) osPriorityHigh,
};
/* Definitions for Task_UART_Rx */
osThreadId_t Task_UART_RxHandle;
const osThreadAttr_t Task_UART_Rx_attributes = {
  .name = "Task_UART_Rx",
  .stack_size = 256 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};
/* Definitions for Task_Alert */
osThreadId_t Task_AlertHandle;
const osThreadAttr_t Task_Alert_attributes = {
  .name = "Task_Alert",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};
/* Definitions for q_dms_state */
osMessageQueueId_t q_dms_stateHandle;
const osMessageQueueAttr_t q_dms_state_attributes = {
  .name = "q_dms_state"
};

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN FunctionPrototypes */

/* USER CODE END FunctionPrototypes */

void StartTaskWatchdog(void *argument);
void StartTaskCanTx(void *argument);
void StartTaskUartRx(void *argument);
void StartTaskAlert(void *argument);

void MX_FREERTOS_Init(void); /* (MISRA C 2004 rule 8.1) */

/**
  * @brief  FreeRTOS initialization
  * @param  None
  * @retval None
  */
void MX_FREERTOS_Init(void) {
  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* USER CODE BEGIN RTOS_MUTEX */
  /* add mutexes, ... */
  /* USER CODE END RTOS_MUTEX */

  /* USER CODE BEGIN RTOS_SEMAPHORES */
  /* add semaphores, ... */
  /* USER CODE END RTOS_SEMAPHORES */

  /* USER CODE BEGIN RTOS_TIMERS */
  /* start timers, add new ones, ... */
  /* USER CODE END RTOS_TIMERS */

  /* Create the queue(s) */
  /* creation of q_dms_state */
  q_dms_stateHandle = osMessageQueueNew (8, sizeof(uint16_t), &q_dms_state_attributes);

  /* USER CODE BEGIN RTOS_QUEUES */
  /* add queues, ... */
  /* USER CODE END RTOS_QUEUES */

  /* Create the thread(s) */
  /* creation of Task_Watchdog */
  Task_WatchdogHandle = osThreadNew(StartTaskWatchdog, NULL, &Task_Watchdog_attributes);

  /* creation of Task_CAN_Tx */
  Task_CAN_TxHandle = osThreadNew(StartTaskCanTx, NULL, &Task_CAN_Tx_attributes);

  /* creation of Task_UART_Rx */
  Task_UART_RxHandle = osThreadNew(StartTaskUartRx, NULL, &Task_UART_Rx_attributes);

  /* creation of Task_Alert */
  Task_AlertHandle = osThreadNew(StartTaskAlert, NULL, &Task_Alert_attributes);

  /* USER CODE BEGIN RTOS_THREADS */
  /* add threads, ... */
  /* USER CODE END RTOS_THREADS */

  /* USER CODE BEGIN RTOS_EVENTS */
  /* add events, ... */
  /* USER CODE END RTOS_EVENTS */

}

/* USER CODE BEGIN Header_StartTaskWatchdog */
/**
  * @brief  Function implementing the Task_Watchdog thread.
  * @param  argument: Not used
  * @retval None
  */
/* USER CODE END Header_StartTaskWatchdog */
void StartTaskWatchdog(void *argument)
{
  /* USER CODE BEGIN StartTaskWatchdog */
  /* Infinite loop */
	for(;;)
	{
		if(curr_seq == last_seq)
		{
			hb_fail_count++;
		}
		else
		{
			hb_fail_count = 0;
			rpi_alive = 1;
			last_seq = curr_seq;
		}

		if(hb_fail_count >= 5)
		{
			rpi_alive = 0;
		}

		// DTC 송출 (베어메탈 while루프 부분, 로직 동일)
		if(rpi_alive == 0 && dtc_sent == 0)
		{
			CAN_TxHeaderTypeDef DtcHeader;
			uint8_t DtcData[8] = {0xFF, 0x01, 0x02, 0x01, 0, 0, 0, 0};
			uint32_t DtcMailbox;

			DtcHeader.StdId = 0x7DF;
			DtcHeader.IDE = CAN_ID_STD;
			DtcHeader.RTR = CAN_RTR_DATA;
			DtcHeader.DLC = 8;
			DtcHeader.TransmitGlobalTime = DISABLE;

			HAL_CAN_AddTxMessage(&hcan1, &DtcHeader, DtcData, &DtcMailbox);
			dtc_sent = 1;
		}
		else if (rpi_alive == 1)
		{
			dtc_sent = 0;
		}

		osDelay(100);
	}
  /* USER CODE END StartTaskWatchdog */
}

/* USER CODE BEGIN Header_StartTaskCanTx */
/**
* @brief Function implementing the Task_CAN_Tx thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartTaskCanTx */
void StartTaskCanTx(void *argument)
{
  /* USER CODE BEGIN StartTaskCanTx */
	CAN_TxHeaderTypeDef TxHeader;
	uint8_t TxData[3];
	uint32_t TxMailbox;
	uint8_t hb_tx_counter = 0;
	uint8_t stm32_hb_count = 0;

	TxHeader.IDE = CAN_ID_STD;
	TxHeader.RTR = CAN_RTR_DATA;
	TxHeader.TransmitGlobalTime = DISABLE;
  /* Infinite loop */
	for(;;)
  	{
	  // 0x100: 졸음 상태
	  TxHeader.StdId = 0x100;
	  TxHeader.DLC = 3;
	  TxData[0] = driver_state;
	  TxData[1] = rpi_alive;
	  TxData[2] = curr_ear; // 예비 바이트 -> ear 정보로 활용
	  HAL_CAN_AddTxMessage(&hcan1, &TxHeader, TxData, &TxMailbox);

	  // 0x200 : ECU Heartbeat (5회마다 500ms)
	  hb_tx_counter++;
	  if(hb_tx_counter >=5)
	  {
		  hb_tx_counter = 0;
		  stm32_hb_count++;
		  TxHeader.StdId = 0x200;
		  TxHeader.DLC = 1;
		  uint8_t HbData[1] = {stm32_hb_count};
		  HAL_CAN_AddTxMessage(&hcan1, &TxHeader, HbData, &TxMailbox);
	  }

	  osDelay(100);
  	}
  /* USER CODE END StartTaskCanTx */
}

/* USER CODE BEGIN Header_StartTaskUartRx */
/**
* @brief Function implementing the Task_UART_Rx thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartTaskUartRx */
void StartTaskUartRx(void *argument)
{
  /* USER CODE BEGIN StartTaskUartRx */
  /* Infinite loop */
  for(;;)
  {
    osDelay(1);
  }
  /* USER CODE END StartTaskUartRx */
}

/* USER CODE BEGIN Header_StartTaskAlert */
/**
* @brief Function implementing the Task_Alert thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartTaskAlert */
void StartTaskAlert(void *argument)
{
  /* USER CODE BEGIN StartTaskAlert */
	uint16_t msg;
	uint8_t state = 0;
	/* Infinite loop */
	for(;;)
	{
		// 큐에서 새 상태 대기, 최대 100ms 새 메세지 오면 바로 깨어남
		if(osMessageQueueGet(q_dms_stateHandle, &msg, NULL, 100) == osOK)
		{
			state = (uint8_t)(msg >> 8);
		}

		// LED 표시
		if(rpi_alive == 0)
		{
			HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_14);
			osDelay(400);
		}
		else
		{
			switch(state)
			{
				case 0:
				{
					HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_RESET);
					break;
				}

				case 1:
				{
					HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_14);
					osDelay(400);
					break;
				}

				case 2:
				{
					HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_SET);
					break;
				}
			}
		}
	}
  /* USER CODE END StartTaskAlert */
}

/* Private application code --------------------------------------------------*/
/* USER CODE BEGIN Application */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
	if(huart->Instance == UART4)
	{
		if(rx_state == 0)
		{
			if(rx_byte == 0xAA) { rx_state = 1; rx_idx = 0; }
		}
		else if(rx_state == 1)
		{
			rx_buf[rx_idx++] = rx_byte;
			if(rx_idx == 4)
			{
				uint8_t calc = (0xAA + rx_buf[0] + rx_buf[1] + rx_buf[2]) & 0xFF;
				if(calc == rx_buf[3])
				{
					driver_state = rx_buf[0];
					curr_ear = rx_buf[1];
					curr_seq = rx_buf[2];

					// RTOS 추가 상태를 큐로 Alert 태스크에 전달
					// 상위 바이트 = driver_state, 하위 바이트 = ear
					uint16_t msg = ((uint16_t)driver_state << 8) | curr_ear;
					osMessageQueuePut(q_dms_stateHandle, &msg, 0, 0);
					// 마지막 인자 timeout = 0 : ISR에서 블로킹 금지(필수!)
				}
				rx_state = 0;
			}
		}
		HAL_UART_Receive_IT(huart, &rx_byte, 1);
	}
}

void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan)
{
	CAN_RxHeaderTypeDef RxHeader;
	uint8_t RxData[8];

	if(HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &RxHeader, RxData) == HAL_OK)
	{
		switch(RxHeader.StdId)
		{
		case 0x101: break;
		case 0x102: break; // TODO : 운전자 확인 후 알림 리셋하는 코드
		default: break;
		}
	}
}
/* USER CODE END Application */

