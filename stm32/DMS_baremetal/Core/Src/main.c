/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
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
#include "main.h"
#include "can.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

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

/* USER CODE BEGIN PV */
volatile uint8_t last_seq = 0;
volatile uint8_t curr_seq = 0;
volatile uint8_t hb_fail_count = 0;
volatile uint8_t rpi_alive = 1;

uint8_t rx_byte = 0;
uint8_t rx_buf[4];
uint8_t rx_idx = 0;
uint8_t rx_state = 0;
volatile uint8_t driver_state = 0;

// LED 500ms 깜빡임용 카운터 (TIM2 주기*N = 500ms)
// TIM2가 500ms 주기라면 카운터 1번
volatile uint8_t led_toggle_flag = 0;

// DTC를 통해 CAN 버스에 rpi_alive=0을 명시적으로 알릴수있음(다른 ECU 등이 받을 수 있음.
volatile uint8_t dtc_sent = 0;

// 0x200 송신 주기 (100ms 루프 * 5 = 500ms)
volatile uint8_t hb_tx_counter = 0;
volatile uint8_t stm32_hb_count = 0; // 0x200, STM에 대한 Heartbeat -> Rpi5_navi


/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_UART4_Init();
  MX_TIM2_Init();
  MX_CAN1_Init();
  /* USER CODE BEGIN 2 */
  // UART의 수신 시작점으로, 이걸 호출한 시점부터 이후 신호가 올때마다 인터럽트 콜백함수가 불린다.
  // HAL_UART_RxCpltCallback이 자동으로 불림
  // 한 번만 호출하면 되고, 이후로 재호출 되는 구조
  HAL_UART_Receive_IT(&huart4, &rx_byte, 1);

  // 타이머 및 인터럽트 시작 가이드
  HAL_TIM_Base_Start_IT(&htim2);

  CAN_TxHeaderTypeDef TxHeader;
  CAN_RxHeaderTypeDef RxHeader;
  uint8_t TxData[8] = {0x01, 0x02, 0x03};
  uint8_t RxData[8];
  uint32_t TxMailbox;

  HAL_CAN_Start(&hcan1);

  // Tx 설정
  TxHeader.StdId = 0x100;
  TxHeader.IDE = CAN_ID_STD;
  TxHeader.RTR = CAN_RTR_DATA;
  TxHeader.DLC = 3;
  TxHeader.TransmitGlobalTime = DISABLE;

  // 필터 설정(전체 수신)
  CAN_FilterTypeDef FilterConfig;
  FilterConfig.FilterBank = 0;
  FilterConfig.FilterMode = CAN_FILTERMODE_IDMASK;
  FilterConfig.FilterScale = CAN_FILTERSCALE_32BIT;
  FilterConfig.FilterIdHigh = 0x0000;
  FilterConfig.FilterIdLow = 0x0000;      // 추가
  FilterConfig.FilterMaskIdHigh = 0x0000; // 추가
  FilterConfig.FilterMaskIdLow = 0x0000;
  FilterConfig.FilterFIFOAssignment = CAN_RX_FIFO0;
  FilterConfig.FilterActivation = ENABLE;
  HAL_CAN_ConfigFilter(&hcan1, &FilterConfig);
  HAL_CAN_ActivateNotification(&hcan1, CAN_IT_RX_FIFO0_MSG_PENDING);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
	  // CAN Tx = driver_state + rpi_alive 같이 송신
	  TxData[0] = driver_state;
	  TxData[1] = rpi_alive;
	  TxData[2] = 0x00; // 예비용

	  HAL_CAN_AddTxMessage(&hcan1, &TxHeader, TxData, &TxMailbox);

	  // Failsafe : Rpi5 Heartbeat 단절 시 0x7DF 송출(DTC)
	  // rpi_alive가 0이 되는 순간(=AI 노드 다운)을 CAN으로 보고, 매 루프 보내면 버스가 시끄러우니
	  // "0으로 바뀌는 순간 1번" 만 송출함

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

	  else if(rpi_alive == 1)
	  {
		  dtc_sent = 0;
	  }

	  if( rpi_alive == 0 )
	  {
		  if(led_toggle_flag)
		  {
			  led_toggle_flag = 0;
			  HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_14);
		  }
	  }
	  else
	  {
		  switch(driver_state)
		  {
			  case 0:
				  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_RESET);
				  break;

			  case 1:
				  if(led_toggle_flag)
				  {
					  led_toggle_flag = 0;
					  HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_14);
				  }
				  break;

			  case 2:
				  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_SET);
				  break;

			  default:
				  break;
		  }
	  }

	  hb_tx_counter++;
	  if(hb_tx_counter >= 5)
	  {
		  hb_tx_counter = 0;
		  stm32_hb_count++; // 롤오버 되는 카운터

		  CAN_TxHeaderTypeDef HbHeader;
		  uint8_t HbData[1] = {stm32_hb_count};
		  uint32_t HbMailbox;

		  HbHeader.StdId = 0x200;
		  HbHeader.IDE = CAN_ID_STD;
		  HbHeader.RTR = CAN_RTR_DATA;
		  HbHeader.DLC = 1;
		  HbHeader.TransmitGlobalTime = DISABLE;

		  HAL_CAN_AddTxMessage(&hcan1, &HbHeader, HbData, &HbMailbox);
	  }
	  HAL_Delay(100);
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_MSI;
  RCC_OscInitStruct.MSIState = RCC_MSI_ON;
  RCC_OscInitStruct.MSICalibrationValue = 0;
  RCC_OscInitStruct.MSIClockRange = RCC_MSIRANGE_6;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_MSI;
  RCC_OscInitStruct.PLL.PLLM = 1;
  RCC_OscInitStruct.PLL.PLLN = 40;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV7;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */

// 인터럽트 콜백함수 작성
// UART가 여러개일 수 있으니 UART4 일때만 실행되도록 Instance랑 비교.
// UART4로 1바이트 수신 완료될 때마다 HAL이 자동으로 호출되는 구조 ?
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
	if( huart->Instance == UART4 )
	{
		// 상태머신으로 프레임 파싱
		// 완성되면 driver_state 업데이트 할 것
		if(rx_state ==0)
		{
			if(rx_byte == 0xAA)
			{
				rx_state = 1;
				rx_idx =0;
			}
		}
		else if(rx_state == 1)
		{
			rx_buf[rx_idx++] = rx_byte; // rx_buf에 rx_byte 저장 후 rx_idx 1 증가
			if(rx_idx == 4) // rx_idx = 4가 되었는지 확인 -> 4개를 다 받았다는 소리
			{
				uint8_t calc = (0xAA + rx_buf[0] + rx_buf[1] + rx_buf[2]) & 0xFF; // CheckSum
				if(calc == rx_buf[3])
				{
					driver_state = rx_buf[0]; // 일치하면 driver_state = rx_buf[0]; 업데이트
					curr_seq = rx_buf[2];
				}
				rx_state = 0; // 다음 프레임 위해 rx_state를 0으로 리셋
			}
		}
		HAL_UART_Receive_IT(huart, &rx_byte, 1); // 다음 바이트 대기
	}
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef * htim)
{
	if(htim -> Instance == TIM2)
	{
		// Heartbeat 검사
		if( curr_seq == last_seq )
		{
			hb_fail_count++;
		}
		else
		{
			hb_fail_count =0;
			rpi_alive = 1;
			last_seq = curr_seq; // 중요
		}

		if(hb_fail_count >= 3)
		{
			rpi_alive = 0;
		}

		// LED 토글 플레그 세팅, TIM2 주기마다 플래그 울림 -> while에서 처리
		led_toggle_flag = 1;
	}
}

void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan)
{
	CAN_RxHeaderTypeDef RxHeader;
	uint8_t RxData[8];

	if(HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &RxHeader, RxData) == HAL_OK)
	{
		switch (RxHeader.StdId)
		{
			case 0x101:
				// 필요 시 ack 수신 플래그 처리 ( 현재는 수신 확인만)
				break;

			case 0x102:
				HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_14);
				break;

			default:
				break;
		}
	}
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
