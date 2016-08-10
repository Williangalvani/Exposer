#include "exposer.h"

Exposer* exposer = &Exposer::self();

uint8_t led = 0;

void setup()
{
	Serial.begin(115200);
	pinMode(13, OUTPUT);
	exposer->registerVariable(VARNAME(led), Exposer::_uint8_t, &led);
}

void loop()
{
	digitalWrite(13,(led>100));
	
	if(Serial.available())
	{
		uint8_t data = Serial.read();
		exposer->processByte(data);
	}
}

