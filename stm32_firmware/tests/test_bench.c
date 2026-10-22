#include "device.h"
#include "app_config.h"
#include "fpga_link.h"
#include "protocol.h"
#include "crc32.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static uint32_t now, fpga_generation;
static bool link_ok=true, stop_ok=true, button=false;
static unsigned writes, checks;
static uint8_t reply[1100]; static size_t reply_len;
#define CHECK(x) do { assert(x); ++checks; } while(0)
uint32_t board_millis(void) { return now; }
bool board_stop_pressed(void) { return button; }
bool board_power_good(void) { return true; }
bool board_a_present(void) { return true; }
bool board_b_present(void) { return true; }
bool fpga_link_probe(void) { return link_ok; }
bool fpga_link_stop(void) { return link_ok && stop_ok; }
bool fpga_link_start(void) { return link_ok; }
bool fpga_link_write_channel(uint8_t channel,const channel_config_t *c) {
 CHECK(channel==0 && c!=NULL); ++writes;return link_ok;
}
bool fpga_link_commit(uint32_t generation) { fpga_generation=generation;return link_ok; }
bool fpga_link_status(fpga_status_t *s) { memset(s,0,sizeof(*s));s->active_generation=fpga_generation;return link_ok; }
bool fpga_link_select_preset(uint8_t x) { (void)x;return false; }
bool fpga_link_data_begin(uint32_t x) { (void)x;return false; }
bool fpga_link_data_write(uint32_t x,const uint8_t *p,size_t n) { (void)x;(void)p;(void)n;return false; }
bool fpga_link_data_end(uint32_t x) { (void)x;return false; }
const char *fpga_link_version(void) { return "FPGA-2.0.0"; }
void ui_force_refresh(void) { }
uint32_t transport_rx_overflows(void) { return 0; }
void transport_write(const uint8_t *p,size_t n) { assert(n<=sizeof(reply));memcpy(reply,p,n);reply_len=n; }
bool storage_save_profile(uint8_t id,const channel_config_t *p) { (void)id;(void)p;return false; }
bool storage_load_profile(uint8_t id,channel_config_t *p) { (void)id;(void)p;return false; }
static void put16(uint8_t *p,uint16_t n) { p[0]=n;p[1]=n>>8; }
static void put32(uint8_t *p,uint32_t n) { for(unsigned j=0;j<4;j++)p[j]=(uint8_t)(n>>(8*j)); }
static void request(uint16_t cmd,const char *json,bool expect_error) {
 static uint16_t seq;uint8_t f[1100];size_t n=strlen(json); ++seq;
 f[0]=0xa5;f[1]=0x5a;f[2]=1;f[3]=1;put16(f+4,cmd);put16(f+6,seq);put32(f+8,(uint32_t)n);
 memcpy(f+12,json,n);put32(f+12+n,crc32_compute(f+2,n+10));reply_len=0;
 /* Deliberately split a frame across two feed calls. */
 protocol_feed(f,7);protocol_poll();CHECK(reply_len==0);
 protocol_feed(f+7,n+9);protocol_poll();CHECK(reply_len>=16);
 CHECK(((reply[3]&4)!=0)==expect_error);
 uint32_t crc;memcpy(&crc,reply+reply_len-4,4);CHECK(crc==crc32_compute(reply+2,reply_len-6));
 reply[reply_len-4]=0;
}
int main(void) {
 CHECK(crc32_compute((const uint8_t*)"123456789",9)==0xcbf43926u);
 device_init();protocol_init();CHECK(g_device.state==DEVICE_IDLE);CHECK(g_device.transfer_valid);
 CHECK(!device_start());request(1,"{}",false);CHECK(strstr((char*)reply+12,"\"channels\":1")!=NULL);
 request(2,"{}",false);CHECK(strstr((char*)reply+12,"\"power_good\":null")!=NULL);
 request(0x10,"{\"channel\":2}",true);
 request(0x10,"{\"channel\":1,\"amplitude_v\":1}",true);
 request(0x10,"{\"channel\":1,\"dac_amplitude_code\":256}",true);
 request(0x10,"{\"channel\":1,\"dac_amplitude_code\":224,\"dac_baseline_code\":16,\"decay_us\":12,\"mean_interval_us\":1000}",false);
 request(0x11,"{}",false);CHECK(writes==1 && g_device.config_generation==1);
 request(0x30,"{}",false);CHECK(g_device.state==DEVICE_RUNNING);
 request(0x11,"{}",true);request(0x31,"{}",false);CHECK(g_device.state==DEVICE_IDLE);
 request(0x10,"{\"channel\":1,\"dac_amplitude_code\":112,\"decay_us\":24,\"mean_interval_us\":2000}",false);
 request(0x11,"{}",false);request(0x30,"{}",false);
 now=2100;device_poll();CHECK(g_device.state==DEVICE_ERROR && g_device.error==DEV_ERR_TRANSFER);
 request(0x70,"{}",false);CHECK(g_device.state==DEVICE_IDLE);
 channel_config_t c=g_device.shadow[0];c.decay_us=NAN;CHECK(!device_set_channel(0,&c));
 c=g_device.shadow[0];c.noise_percent=1;CHECK(!device_set_channel(0,&c));
 c=g_device.shadow[0];c.decay_us=100;c.interval_us=128;CHECK(!device_set_channel(0,&c));
 stop_ok=false;request(0x31,"{}",true);CHECK(g_device.state==DEVICE_ERROR && !g_device.fpga_online);
 stop_ok=true;CHECK(device_clear_error());g_device.last_host_ms=now;
 CHECK(device_commit());CHECK(device_start());link_ok=false;now+=100;device_poll();
 CHECK(g_device.state==DEVICE_ERROR && !g_device.fpga_online);
 link_ok=true;CHECK(device_clear_error());CHECK(device_commit());CHECK(device_start());
 button=true;device_poll();CHECK(g_device.state==DEVICE_IDLE);
 printf("PASS: STM32 bench %u checks (mock FPGA and GPIO)\n",checks);return 0;
}
