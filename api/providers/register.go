package providers

func init() {
	MustRegister(NewKilterProvider())
	MustRegister(NewCruxProvider())
}
