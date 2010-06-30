$(document).ready(function(){
    $(".delete").click(function(e){
        e.preventDefault();
        if(confirm("Are you sure? There's no turning back!")){
            var obj = $(this);
            var url = obj.attr('href');
            $.ajax({
                url: url,
                type: 'post',
                success: function(){
                    obj.parent().parent().fadeOut().remove();
                },
                error: function(){
                    alert("Oops, something strange happened. Care to try again?");
                }
            })
        }
        return false;
    })
})
