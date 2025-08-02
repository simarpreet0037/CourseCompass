from django import forms

class CourseForm(forms.Form):
    code = forms.CharField(label='Course Code', max_length=10)
    title = forms.CharField(label='Course Title', max_length=100)
    credits = forms.IntegerField(label='Credits', min_value=1, max_value=6)
    level = forms.ChoiceField(
        choices=[(100, "100"), (200, "200"), (300, "300"), (400, "400")],
        label='Course Level'
    )
